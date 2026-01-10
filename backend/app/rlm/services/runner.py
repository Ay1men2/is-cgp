from __future__ import annotations

"""Compatibility layer for legacy imports."""

from typing import Any

from app.rlm.services.program_runner import (
    ProgramLimitError,
    ProgramParseError,
    RunnerOutcome,
    build_limits_snapshot,
    deterministic_fallback,
    run_program,
)
from app.rlm.services.run_pipeline import (
    ExecutionResult,
    MockExecutor,
    MockRootLM,
    ProgramExecutor,
    RootLMClient,
    RootLMFinalResult,
    RootLMProgramResult,
    RunResult,
    run_rlm,
)


def normalize_limits_options(options: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    options_snapshot = dict(options or {})
    raw_limits = options_snapshot.get("limits")
    limits_source = raw_limits if isinstance(raw_limits, dict) else options_snapshot
    limits = build_limits_snapshot(limits_source)
    if isinstance(raw_limits, dict):
        options_snapshot["limits_snapshot"] = limits
    else:
        options_snapshot["limits"] = limits
    return options_snapshot, limits


__all__ = [
    "ProgramLimitError",
    "ProgramParseError",
    "RunnerOutcome",
    "build_limits_snapshot",
    "deterministic_fallback",
    "run_program",
    "ExecutionResult",
    "MockExecutor",
    "MockRootLM",
    "ProgramExecutor",
    "RootLMClient",
    "RootLMFinalResult",
    "RootLMProgramResult",
    "RunResult",
    "run_rlm",
    "normalize_limits_options",
]
