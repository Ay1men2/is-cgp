"""Backward-compatible exports for legacy imports."""

from app.rlm.services.program_runner import (
    ProgramLimitError,
    ProgramParseError,
    RunnerOutcome,
    build_limits_snapshot,
    deterministic_fallback,
    run_program,
)
from app.rlm.services.rlm_pipeline import (
    ExecutionResult,
    MockExecutor,
    MockRootLM,
    RootLMFinalResult,
    RootLMProgramResult,
    RunResult,
    run_rlm,
)

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
    "RootLMFinalResult",
    "RootLMProgramResult",
    "RunResult",
    "run_rlm",
]
