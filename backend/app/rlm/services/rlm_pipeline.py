from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.rlm.adapters.repos_sql import RlmRepoSQL
from app.rlm.domain.models import CandidateIndex
from app.rlm.services.retrieval import build_candidate_index


class RootLMClient(Protocol):
    def generate_program(
        self,
        index: CandidateIndex,
        policy: dict[str, Any],
        limits: dict[str, Any],
        options: dict[str, Any],
    ) -> "RootLMProgramResult":
        ...

    def generate_final(
        self,
        index: CandidateIndex,
        evidence: list[dict[str, Any]],
        subcalls: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> "RootLMFinalResult":
        ...


class ProgramExecutor(Protocol):
    def execute(
        self,
        program: dict[str, Any],
        index: CandidateIndex,
        options: dict[str, Any],
    ) -> "ExecutionResult":
        ...


@dataclass
class RootLMProgramResult:
    program: dict[str, Any]
    meta: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] | None = None


@dataclass
class RootLMFinalResult:
    final: dict[str, Any]
    meta: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] | None = None


@dataclass
class ExecutionResult:
    events: list[dict[str, Any]] = field(default_factory=list)
    glimpses: list[dict[str, Any]] = field(default_factory=list)
    subcalls: list[dict[str, Any]] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    run_id: str
    status: str
    final: dict[str, Any]
    program: dict[str, Any] = field(default_factory=dict)
    glimpses: list[dict[str, Any]] = field(default_factory=list)
    subcalls: list[dict[str, Any]] = field(default_factory=list)
    final_answer: str | None = None
    citations: list[Any] = field(default_factory=list)


class MockRootLM:
    def generate_program(
        self,
        index: CandidateIndex,
        policy: dict[str, Any],
        limits: dict[str, Any],
        options: dict[str, Any],
    ) -> RootLMProgramResult:
        candidate_ids = [candidate.artifact_id for candidate in index.candidates]
        program = options.get("program")
        if program is None:
            program = {
                "policy": policy,
                "limits": limits,
                "candidate_ids": candidate_ids,
                "steps": [],
            }
        meta = {
            "mode": "mock",
            "policy": policy,
            "limits": limits,
        }
        return RootLMProgramResult(program=program, meta=meta, raw={"mock": True})

    def generate_final(
        self,
        index: CandidateIndex,
        evidence: list[dict[str, Any]],
        subcalls: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> RootLMFinalResult:
        answer = options.get("final_answer")
        if answer is None:
            answer = f"Mock answer for: {index.query}"
        final = {
            "answer": answer,
            "citations": list(options.get("citations") or []),
            "evidence_count": len(evidence),
            "subcall_count": len(subcalls),
        }
        return RootLMFinalResult(final=final, meta={"mode": "mock"}, raw={"mock": True})


class MockExecutor:
    def execute(
        self,
        program: dict[str, Any],
        index: CandidateIndex,
        options: dict[str, Any],
    ) -> ExecutionResult:
        return ExecutionResult(
            events=list(options.get("events") or []),
            glimpses=list(options.get("glimpses") or []),
            subcalls=list(options.get("subcalls") or []),
            variables=dict(options.get("vars") or {}),
            status=str(options.get("executor_status") or "ok"),
            meta={"mode": "mock", "program_summary": program.get("steps")},
        )


def run_rlm(
    repo: RlmRepoSQL,
    session_id: str,
    query: str,
    options: dict[str, Any] | None = None,
    *,
    rootlm: RootLMClient | None = None,
    executor: ProgramExecutor | None = None,
) -> RunResult:
    options = options or {}
    rootlm = rootlm or MockRootLM()
    executor = executor or MockExecutor()

    index = build_candidate_index(repo, session_id, query, options)
    run_id = repo.insert_run(
        session_id=session_id,
        query=query,
        options=options,
        candidate_index=index.model_dump(),
    )

    status = "ok"
    errors: list[dict[str, Any]] = []
    meta: dict[str, Any] = {
        "round0": {
            "candidate_count": len(index.candidates),
        }
    }
    program: dict[str, Any] = {}
    events: list[dict[str, Any]] = []
    glimpses: list[dict[str, Any]] = []
    glimpses_meta: list[dict[str, Any]] = []
    subcalls: list[dict[str, Any]] = []
    final: dict[str, Any] = {}
    final_answer: str | None = None
    citations: list[Any] = []

    try:
        policy = dict(options.get("policy") or {})
        limits = dict(options.get("limits") or {})
        program_result = rootlm.generate_program(index, policy, limits, options)
        program = program_result.program
        meta["round1"] = {
            **program_result.meta,
            "policy": policy,
            "limits": limits,
        }
    except Exception as exc:
        status = "error"
        errors.append({"stage": "round1", "error": str(exc)})

    repo.update_run_payload(
        run_id,
        program=program,
        meta=meta,
        events=events,
        glimpses=glimpses,
        glimpses_meta=glimpses_meta,
        subcalls=subcalls,
        final=final,
        final_answer=final_answer,
        citations=citations,
        status=status,
        errors=errors,
    )

    if status != "ok":
        return RunResult(
            run_id=run_id,
            status=status,
            final=final,
            program=program,
            glimpses=glimpses,
            subcalls=subcalls,
            final_answer=final_answer,
            citations=citations,
        )

    try:
        execution = executor.execute(program, index, options)
        events = list(execution.events)
        glimpses = list(execution.glimpses)
        glimpses_meta = list(options.get("glimpses_meta") or [])
        if not glimpses_meta:
            glimpses_meta = [
                item.get("glimpse_meta")
                for item in glimpses
                if isinstance(item, dict) and item.get("glimpse_meta")
            ]
        subcalls = list(execution.subcalls)
        meta["round2"] = {
            **execution.meta,
            "vars": dict(execution.variables),
            "status": execution.status,
        }
        status = execution.status or status
    except Exception as exc:
        status = "error"
        errors.append({"stage": "round2", "error": str(exc)})

    repo.update_run_payload(
        run_id,
        program=program,
        meta=meta,
        events=events,
        glimpses=glimpses,
        glimpses_meta=glimpses_meta,
        subcalls=subcalls,
        final=final,
        final_answer=final_answer,
        citations=citations,
        status=status,
        errors=errors,
    )

    if status != "ok":
        return RunResult(
            run_id=run_id,
            status=status,
            final=final,
            program=program,
            glimpses=glimpses,
            subcalls=subcalls,
            final_answer=final_answer,
            citations=citations,
        )

    try:
        evidence = [{"events": events}, {"glimpses": glimpses}]
        final_result = rootlm.generate_final(index, evidence, subcalls, options)
        final = final_result.final
        final_answer = str(final.get("answer")) if final.get("answer") is not None else None
        citations = list(final.get("citations") or [])
        meta["round3"] = {
            **final_result.meta,
            "evidence_items": len(evidence),
        }
    except Exception as exc:
        status = "error"
        errors.append({"stage": "round3", "error": str(exc)})

    repo.update_run_payload(
        run_id,
        program=program,
        meta=meta,
        events=events,
        glimpses=glimpses,
        glimpses_meta=glimpses_meta,
        subcalls=subcalls,
        final=final,
        final_answer=final_answer,
        citations=citations,
        status=status,
        errors=errors,
    )

    return RunResult(
        run_id=run_id,
        status=status,
        final=final,
        program=program,
        glimpses=glimpses,
        subcalls=subcalls,
        final_answer=final_answer,
        citations=citations,
    )
