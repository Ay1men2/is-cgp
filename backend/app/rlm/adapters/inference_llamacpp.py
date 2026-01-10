from __future__ import annotations

import shlex
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Iterable

from app.rlm.adapters.inference_adapter import InferenceAdapter


@dataclass(frozen=True)
class RetryPolicy:
    timeout_s: float = 30.0
    max_retries: int = 2
    backoff_s: float = 1.0


def run_llama_cli(
    *,
    llama_cli_path: str,
    model_path: str,
    prompt: str,
    ctx_size: int | None = None,
    n_predict: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    extra_args: Iterable[str] | None = None,
    retry: RetryPolicy | None = None,
) -> str:
    policy = retry or RetryPolicy()
    cmd = [
        llama_cli_path,
        "-m",
        model_path,
        "-p",
        prompt,
    ]
    if ctx_size is not None:
        cmd.extend(["-c", str(ctx_size)])
    if n_predict is not None:
        cmd.extend(["-n", str(n_predict)])
    if temperature is not None:
        cmd.extend(["--temp", str(temperature)])
    if top_p is not None:
        cmd.extend(["--top-p", str(top_p)])
    if extra_args:
        cmd.extend(list(extra_args))

    last_error: Exception | None = None
    for attempt in range(policy.max_retries + 1):
        try:
            completed = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=policy.timeout_s,
            )
            return completed.stdout.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            last_error = exc
            if attempt >= policy.max_retries:
                break
            time.sleep(policy.backoff_s)

    cmd_str = " ".join(shlex.quote(part) for part in cmd)
    raise RuntimeError(f"llama-cli failed after retries: {cmd_str} ({last_error})")


class InferenceLlamaCliAdapter(InferenceAdapter):
    def __init__(
        self,
        *,
        llama_cli_path: str,
        default_model: str | None = None,
        default_ctx_size: int | None = None,
        default_max_tokens: int | None = None,
        default_temperature: float | None = None,
        default_top_p: float | None = None,
        default_extra_args: Iterable[str] | None = None,
        retry: RetryPolicy | None = None,
    ) -> None:
        self._llama_cli_path = llama_cli_path
        self._default_model = default_model
        self._default_ctx_size = default_ctx_size
        self._default_max_tokens = default_max_tokens
        self._default_temperature = default_temperature
        self._default_top_p = default_top_p
        self._default_extra_args = list(default_extra_args or [])
        self._retry = retry or RetryPolicy()

    def generate(
        self,
        prompt: str,
        timeout_s: float | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        opts = options or {}
        model_path = opts.get("model") or self._default_model
        if not model_path:
            raise ValueError("llama-cli model path is required for inference.")

        ctx_size = opts.get("ctx_size", self._default_ctx_size)
        max_tokens = opts.get("max_tokens", self._default_max_tokens)
        temperature = opts.get("temperature", self._default_temperature)
        top_p = opts.get("top_p", self._default_top_p)
        extra_args = list(self._default_extra_args)
        extra_args.extend(opts.get("extra_args") or [])

        retry = self._retry
        if timeout_s is not None:
            retry = RetryPolicy(
                timeout_s=timeout_s,
                max_retries=self._retry.max_retries,
                backoff_s=self._retry.backoff_s,
            )

        return run_llama_cli(
            llama_cli_path=self._llama_cli_path,
            model_path=model_path,
            prompt=prompt,
            ctx_size=ctx_size,
            n_predict=max_tokens,
            temperature=temperature,
            top_p=top_p,
            extra_args=extra_args,
            retry=retry,
        )
