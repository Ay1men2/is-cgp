from __future__ import annotations

from typing import Any, Protocol


class InferenceAdapter(Protocol):
    def generate(
        self,
        prompt: str,
        timeout_s: float | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        raise NotImplementedError
