from __future__ import annotations

from typing import Callable


class LlmJudge:
    def __init__(
        self,
        plan_call: Callable[[str, float | None], str],
        decision_call: Callable[[str, float | None], str],
    ) -> None:
        self._plan_call = plan_call
        self._decision_call = decision_call

    def plan(self, prompt: str, *, timeout_s: float | None = None) -> str:
        return self._plan_call(prompt, timeout_s)

    def decision(self, prompt: str, *, timeout_s: float | None = None) -> str:
        return self._decision_call(prompt, timeout_s)
