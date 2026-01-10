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
    options_snapshot, limits = normalize_limits_options(options)
    run_id = repo.insert_run(
        session_id=session_id,
        query=query,
        options=options_snapshot,
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
        policy = dict(options_snapshot.get("policy") or {})
        program_result = rootlm.generate_program(index, policy, limits, options_snapshot)
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
        execution = executor.execute(program, index, options_snapshot)
        events = list(execution.events)
        glimpses = list(execution.glimpses)
        glimpses_meta = list(options_snapshot.get("glimpses_meta") or [])
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
        final_result = rootlm.generate_final(index, evidence, subcalls, options_snapshot)
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
import json
from dataclasses import dataclass
from typing import Any, Iterable

from app.rlm.domain.models import Candidate, CandidateIndex
from app.rlm.services.executor import ExecutionLimits, ProgramExecutor


_DEFAULT_LIMITS = {
    "max_steps": 16,
    "max_subcalls": 24,
    "max_depth": 4,
    "max_program_chars": 20_000,
    "max_event_errors": 2,
}


class ProgramParseError(ValueError):
    pass


class ProgramLimitError(ValueError):
    def __init__(self, limit: str, value: int, max_value: int) -> None:
        super().__init__(f"{limit} exceeded: {value} > {max_value}")
        self.limit = limit
        self.value = value
        self.max_value = max_value


@dataclass
class RunnerOutcome:
    status: str
    assembled_context: dict[str, Any]
    errors: list[dict[str, Any]]
    events: list[dict[str, Any]]
    degraded: bool


def build_limits_snapshot(options: dict[str, Any]) -> dict[str, int]:
    limits: dict[str, int] = {}
    for key, default in _DEFAULT_LIMITS.items():
        raw = options.get(key, default)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = int(default)
        if value <= 0:
            value = int(default)
        limits[key] = value
    return limits


def normalize_limits_options(options: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    options_snapshot = dict(options)
    raw_limits = options_snapshot.get("limits")
    limits_source = raw_limits if isinstance(raw_limits, dict) else options_snapshot
    limits = build_limits_snapshot(limits_source)
    if isinstance(raw_limits, dict):
        options_snapshot["limits_snapshot"] = limits
    else:
        options_snapshot["limits"] = limits
    return options_snapshot, limits


def _clamp_int(value: Any, *, default: int, lo: int, hi: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if number < lo:
        return lo
    if number > hi:
        return hi
    return number


def _extract_program(raw_program: Any) -> Iterable[dict[str, Any]]:
    if raw_program is None:
        return []
    if isinstance(raw_program, list):
        return raw_program
    if isinstance(raw_program, dict):
        if "steps" in raw_program:
            return raw_program["steps"]
        if "program" in raw_program:
            return raw_program["program"]
        return [raw_program]
    if isinstance(raw_program, str):
        text = raw_program.strip()
        if not text:
            return []
        data = json.loads(text)
        return _extract_program(data)
    raise ProgramParseError("program must be list, dict, or json string")


def _estimate_program_chars(raw_program: Any) -> int:
    if raw_program is None:
        return 0
    if isinstance(raw_program, str):
        return len(raw_program)
    try:
        return len(json.dumps(raw_program))
    except TypeError:
        return len(str(raw_program))


def _check_limits(program: Iterable[dict[str, Any]], limits: dict[str, int]) -> None:
    max_steps = limits["max_steps"]
    max_subcalls = limits["max_subcalls"]
    max_depth = limits["max_depth"]
    step_count = 0
    subcall_count = 0

    def _walk(steps: Iterable[dict[str, Any]], depth: int) -> None:
        nonlocal step_count, subcall_count
        if depth > max_depth:
            raise ProgramLimitError("max_depth", depth, max_depth)
        for step in steps:
            step_count += 1
            if step_count > max_steps:
                raise ProgramLimitError("max_steps", step_count, max_steps)
            subcalls = step.get("subcalls") or []
            if subcalls:
                if not isinstance(subcalls, list):
                    raise ProgramParseError("subcalls must be a list")
                subcall_count += len(subcalls)
                if subcall_count > max_subcalls:
                    raise ProgramLimitError("max_subcalls", subcall_count, max_subcalls)
                _walk(subcalls, depth + 1)

    _walk(list(program), depth=1)


def _fallback_candidates(index: CandidateIndex, *, top_k: int) -> list[Candidate]:
    return sorted(
        index.candidates,
        key=lambda candidate: (
            candidate.pinned,
            candidate.weight,
            float(candidate.score_breakdown.get("hit_count") or 0.0),
            candidate.base_score,
        ),
        reverse=True,
    )[:top_k]


def deterministic_fallback(index: CandidateIndex, *, top_k: int) -> dict[str, Any]:
    selected = _fallback_candidates(index, top_k=top_k)
    return {
        "mode": "deterministic_fallback",
        "selected_ids": [candidate.artifact_id for candidate in selected],
        "selected": [
            {
                "artifact_id": candidate.artifact_id,
                "pinned": candidate.pinned,
                "weight": candidate.weight,
                "hit_count": candidate.score_breakdown.get("hit_count", 0.0),
            }
            for candidate in selected
        ],
    }


def run_program(
    index: CandidateIndex,
    options: dict[str, Any],
    *,
    limits: dict[str, int],
) -> RunnerOutcome:
    raw_program = options.get("program")
    fallback_top_k = _clamp_int(options.get("fallback_top_k", 5), default=5, lo=1, hi=200)
    errors: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    try:
        program_chars = _estimate_program_chars(raw_program)
        if program_chars > limits["max_program_chars"]:
            raise ProgramLimitError(
                "max_program_chars", program_chars, limits["max_program_chars"]
            )
        program = _extract_program(raw_program)
        _check_limits(program, limits)
    except ProgramLimitError as exc:
        errors.append(
            {
                "type": "limit_exceeded",
                "limit": exc.limit,
                "value": exc.value,
                "max": exc.max_value,
            }
        )
        return RunnerOutcome(
            status="stopped",
            assembled_context={},
            errors=errors,
            events=events,
            degraded=False,
        )
    except (ProgramParseError, json.JSONDecodeError, TypeError, ValueError) as exc:
        errors.append({"type": "program_parse_failed", "message": str(exc)})
        fallback = deterministic_fallback(index, top_k=fallback_top_k)
        return RunnerOutcome(
            status="degraded",
            assembled_context=fallback,
            errors=errors,
            events=events,
            degraded=True,
        )

    executor = ProgramExecutor(
        ExecutionLimits(
            max_steps=limits["max_steps"],
            max_subcalls=limits["max_subcalls"],
            max_depth=limits["max_depth"],
            max_event_errors=limits["max_event_errors"],
        )
    )
    execution = executor.execute(program)
    events = [event.to_dict() for event in execution.events]
    errors.extend(execution.errors)

    if execution.stopped and execution.errors:
        error_types = {err.get("type") for err in execution.errors}
        if "event_error_threshold" in error_types:
            fallback = deterministic_fallback(index, top_k=fallback_top_k)
            return RunnerOutcome(
                status="degraded",
                assembled_context=fallback,
                errors=errors,
                events=events,
                degraded=True,
            )
        return RunnerOutcome(
            status="stopped",
            assembled_context={},
            errors=errors,
            events=events,
            degraded=False,
        )

    selected_ids = []
    for artifact_id in execution.selected_ids:
        if artifact_id not in selected_ids:
            selected_ids.append(artifact_id)

    return RunnerOutcome(
        status="ok",
        assembled_context={"mode": "program", "selected_ids": selected_ids},
        errors=errors,
        events=events,
        degraded=False,
    )
