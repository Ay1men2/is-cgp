from __future__ import annotations

import shlex
import subprocess
import time
from dataclasses import dataclass
from typing import Iterable


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
