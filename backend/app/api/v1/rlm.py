from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_engine  # 你已有：返回 Engine（有缓存）
from sqlalchemy.engine import Engine

from app.rlm.adapters.repos_sql import RlmRepoSQL
from app.rlm.services.retrieval import build_candidate_index
from app.rlm.services.runner import normalize_limits_options, run_program, run_rlm
from app.rlm.services.runs import create_minimal_run

router = APIRouter(prefix="/rlm", tags=["rlm"])


class RlmAssembleReq(BaseModel):
    session_id: str
    query: str
    options: dict[str, Any] = Field(default_factory=dict)


class RlmAssembleResp(BaseModel):
    run_id: str
    status: str = "ok"
    assembled_context: dict[str, Any] = Field(default_factory=dict)
    rounds_summary: list[dict[str, Any]] = Field(default_factory=list)
    rendered_prompt: Optional[str] = None


class RlmRunReq(BaseModel):
    session_id: str
    query: str
    options: dict[str, Any] = Field(default_factory=dict)


class RlmRunResp(BaseModel):
    run_id: str
    status: str = "ok"
    program: dict[str, Any] = Field(default_factory=dict)
    glimpses: list[dict[str, Any]] = Field(default_factory=list)
    subcalls: list[dict[str, Any]] = Field(default_factory=list)
    final_answer: Optional[str] = None
    citations: list[Any] = Field(default_factory=list)
    final: dict[str, Any] = Field(default_factory=dict)


@router.post("/assemble", response_model=RlmAssembleResp)
def rlm_assemble(req: RlmAssembleReq, engine: Engine = Depends(get_engine)) -> RlmAssembleResp:
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="empty_query_not_allowed")
    repo = RlmRepoSQL(engine)

    try:
        idx = build_candidate_index(repo, req.session_id, req.query, req.options)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    options_snapshot, limits = normalize_limits_options(req.options)

    run_id = repo.insert_run(
        session_id=req.session_id,
        query=req.query,
        options=options_snapshot,
        candidate_index=idx.model_dump(),
    )

    outcome = run_program(idx, options_snapshot, limits=limits)
    repo.finish_run(
        run_id=run_id,
        assembled_context=outcome.assembled_context,
        rendered_prompt=None,
        status=outcome.status,
        errors=outcome.errors,
    )

    return RlmAssembleResp(
        run_id=run_id,
        status=outcome.status,
        assembled_context=outcome.assembled_context,
        rounds_summary=[],
        rendered_prompt=None,
    )


@router.post("/run", response_model=RlmRunResp)
def rlm_run(req: RlmRunReq, engine: Engine = Depends(get_engine)) -> RlmRunResp:
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="empty_query_not_allowed")
    repo = RlmRepoSQL(engine)

    try:
        result = run_rlm(repo, req.session_id, req.query, req.options)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return RlmRunResp(
        run_id=result.run_id,
        status=result.status,
        program=result.program,
        glimpses=result.glimpses,
        subcalls=result.subcalls,
        final_answer=result.final_answer,
        citations=result.citations,
        final=result.final,
    )
