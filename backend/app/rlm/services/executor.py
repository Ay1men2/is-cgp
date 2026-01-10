from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass
class ExecutionEvent:
    step: int
    action: str
    status: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {"step": self.step, "action": self.action, "status": self.status}
        if self.error:
            payload["error"] = self.error
        return payload


@dataclass
class ExecutionResult:
    selected_ids: list[str] = field(default_factory=list)
    events: list[ExecutionEvent] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    stopped: bool = False


@dataclass(frozen=True)
class ExecutionLimits:
    max_steps: int
    max_subcalls: int
    max_depth: int
    max_event_errors: int


class ProgramExecutor:
    def __init__(self, limits: ExecutionLimits) -> None:
        self._limits = limits

    def execute(self, program: Iterable[dict[str, Any]]) -> ExecutionResult:
        result = ExecutionResult()
        error_count = 0
        step_counter = 0
        subcall_counter = 0

        def _record_error(step_index: int, action: str, message: str) -> None:
            nonlocal error_count
            error_count += 1
            result.events.append(
                ExecutionEvent(step=step_index, action=action, status="error", error=message)
            )
            result.errors.append(
                {
                    "type": "event_error",
                    "step": step_index,
                    "action": action,
                    "message": message,
                }
            )

        def _visit_steps(steps: list[dict[str, Any]], depth: int) -> bool:
            nonlocal step_counter, subcall_counter

            if depth > self._limits.max_depth:
                result.errors.append(
                    {
                        "type": "limit_exceeded",
                        "limit": "max_depth",
                        "value": depth,
                        "max": self._limits.max_depth,
                    }
                )
                result.stopped = True
                return False

            for step in steps:
                step_counter += 1
                if step_counter > self._limits.max_steps:
                    result.errors.append(
                        {
                            "type": "limit_exceeded",
                            "limit": "max_steps",
                            "value": step_counter,
                            "max": self._limits.max_steps,
                        }
                    )
                    result.stopped = True
                    return False

                action = str(step.get("action", "noop"))
                try:
                    self._execute_step(step_counter, action, step, result)
                except Exception as exc:  # noqa: BLE001 - executor should capture per-step errors
                    _record_error(step_counter, action, str(exc))

                if error_count > self._limits.max_event_errors:
                    result.errors.append(
                        {
                            "type": "event_error_threshold",
                            "limit": self._limits.max_event_errors,
                            "value": error_count,
                        }
                    )
                    result.stopped = True
                    return False

                subcalls = step.get("subcalls") or []
                if subcalls:
                    if not isinstance(subcalls, list):
                        _record_error(step_counter, action, "subcalls must be a list")
                        if error_count > self._limits.max_event_errors:
                            result.stopped = True
                            return False
                        continue
                    subcall_counter += len(subcalls)
                    if subcall_counter > self._limits.max_subcalls:
                        result.errors.append(
                            {
                                "type": "limit_exceeded",
                                "limit": "max_subcalls",
                                "value": subcall_counter,
                                "max": self._limits.max_subcalls,
                            }
                        )
                        result.stopped = True
                        return False
                    if not _visit_steps(subcalls, depth + 1):
                        return False

            return True

        _visit_steps(list(program), depth=1)
        return result

    def _execute_step(
        self,
        step_index: int,
        action: str,
        payload: dict[str, Any],
        result: ExecutionResult,
    ) -> None:
        if action == "select":
            selected_ids = payload.get("selected_ids")
            if not isinstance(selected_ids, list):
                raise ValueError("select requires selected_ids list")
            for item in selected_ids:
                if not isinstance(item, str) or not item:
                    raise ValueError("select requires non-empty string ids")
            result.selected_ids.extend(selected_ids)
            result.events.append(ExecutionEvent(step=step_index, action=action, status="ok"))
            return

        if action == "noop":
            result.events.append(ExecutionEvent(step=step_index, action=action, status="ok"))
            return

        raise ValueError(f"unsupported action: {action}")
