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
