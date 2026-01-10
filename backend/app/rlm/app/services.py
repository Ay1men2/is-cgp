from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends
from sqlalchemy.engine import Engine

from app.deps import get_engine
from app.rlm.adapters.repos_sql import RlmRepoSQL
from app.rlm.services.assembly_runner import build_limits_snapshot, run_program
from app.rlm.services.retrieval import build_candidate_index
from app.rlm.services.run_pipeline import run_rlm


@dataclass(frozen=True)
class RlmServiceError(Exception):
    status_code: int
    detail: str


class RlmAssembleService:
    def __init__(self, repo: RlmRepoSQL):
        self.repo = repo

    def assemble(
        self,
        session_id: str,
        query: str,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not query.strip():
            raise RlmServiceError(status_code=400, detail="empty_query_not_allowed")
        options = options or {}

        try:
            idx = build_candidate_index(self.repo, session_id, query, options)
        except ValueError as exc:
            raise RlmServiceError(status_code=404, detail=str(exc)) from exc

        options_snapshot = dict(options)
        limits = build_limits_snapshot(options_snapshot)
        if "limits" in options_snapshot:
            options_snapshot["limits_snapshot"] = limits
        else:
            options_snapshot["limits"] = limits

        run_id = self.repo.insert_run(
            session_id=session_id,
            query=query,
            options=options_snapshot,
            candidate_index=idx.model_dump(),
        )

        outcome = run_program(idx, options_snapshot, limits=limits)
        self.repo.finish_run(
            run_id=run_id,
            assembled_context=outcome.assembled_context,
            rendered_prompt=None,
            status=outcome.status,
            errors=outcome.errors,
        )

        return {
            "run_id": run_id,
            "status": outcome.status,
            "assembled_context": outcome.assembled_context,
            "rounds_summary": [],
            "rendered_prompt": None,
        }


class RlmRunService:
    def __init__(self, repo: RlmRepoSQL):
        self.repo = repo

    def run(
        self,
        session_id: str,
        query: str,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not query.strip():
            raise RlmServiceError(status_code=400, detail="empty_query_not_allowed")

        try:
            result = run_rlm(self.repo, session_id, query, options)
        except ValueError as exc:
            raise RlmServiceError(status_code=404, detail=str(exc)) from exc

        return {
            "run_id": result.run_id,
            "status": result.status,
            "program": result.program,
            "glimpses": result.glimpses,
            "subcalls": result.subcalls,
            "final_answer": result.final_answer,
            "citations": result.citations,
            "final": result.final,
        }


def get_rlm_assemble_service(engine: Engine = Depends(get_engine)) -> RlmAssembleService:
    return RlmAssembleService(RlmRepoSQL(engine))


def get_rlm_run_service(engine: Engine = Depends(get_engine)) -> RlmRunService:
    return RlmRunService(RlmRepoSQL(engine))
