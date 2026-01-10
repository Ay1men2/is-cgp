from __future__ import annotations

from typing import Any, Mapping

from app.rlm.adapters.inference_adapter import InferenceAdapter


class InferenceRunner:
    def __init__(
        self,
        adapters: Mapping[str, InferenceAdapter],
        *,
        default_backend: str | None = None,
    ) -> None:
        self._adapters = dict(adapters)
        self._default_backend = default_backend

    def generate(
        self,
        prompt: str,
        *,
        role: str = "root",
        timeout_s: float | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> str:
        options = options or {}
        backend_options = options.get("backend") or {}
        role_options = backend_options.get(role) or {}

        adapter_name = (
            role_options.get("adapter")
            or role_options.get("backend")
            or backend_options.get("adapter")
            or self._default_backend
        )
        if not adapter_name:
            raise ValueError("Inference backend adapter must be specified.")

        adapter = self._adapters.get(adapter_name)
        if adapter is None:
            raise KeyError(f"Inference backend adapter not found: {adapter_name}")

        adapter_options = dict(role_options.get("options") or {})
        if "model" in role_options:
            adapter_options["model"] = role_options["model"]
        if "max_tokens" in role_options:
            adapter_options["max_tokens"] = role_options["max_tokens"]

        role_timeout = role_options.get("timeout_s")
        effective_timeout = timeout_s if timeout_s is not None else role_timeout

        return adapter.generate(prompt, timeout_s=effective_timeout, options=adapter_options)
