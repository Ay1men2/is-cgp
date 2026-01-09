from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


_ROUND_STAGES = ("plan", "examine", "decision")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RoundRecord:
    stage: str
    plan: str = ""
    glimpses: list[dict[str, Any]] = field(default_factory=list)
    decision: dict[str, Any] | None = None
    timing: dict[str, Any] = field(
        default_factory=lambda: {
            "started_at": None,
            "ended_at": None,
            "elapsed_ms": None,
        }
    )
    errors: list[str] = field(default_factory=list)

    def start(self) -> None:
        self.timing["started_at"] = _utc_now().isoformat()

    def end(self) -> None:
        ended_at = _utc_now()
        self.timing["ended_at"] = ended_at.isoformat()
        started_at = self.timing.get("started_at")
        if isinstance(started_at, str):
            try:
                started_dt = datetime.fromisoformat(started_at)
            except ValueError:
                started_dt = None
        else:
            started_dt = None
        if started_dt:
            elapsed = (ended_at - started_dt).total_seconds() * 1000
            self.timing["elapsed_ms"] = round(elapsed, 2)

    def add_error(self, message: str) -> None:
        if message:
            self.errors.append(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "plan": self.plan,
            "glimpses": list(self.glimpses),
            "decision": self.decision,
            "timing": dict(self.timing),
            "errors": list(self.errors),
        }


def build_rounds() -> list[RoundRecord]:
    """
    固定 3 轮：Plan -> Examine -> Decision。
    每轮记录 plan/glimpses/decision/timing/errors。
    """
    return [RoundRecord(stage=stage) for stage in _ROUND_STAGES]


def rounds_to_dicts(rounds: list[RoundRecord]) -> list[dict[str, Any]]:
    return [round_record.to_dict() for round_record in rounds]
