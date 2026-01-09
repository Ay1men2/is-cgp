from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class RetryPolicy:
    timeout_s: float = 30.0
    max_retries: int = 2
    backoff_s: float = 1.0


class VllmChatCompletionsClient:
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        retry: RetryPolicy | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._retry = retry or RetryPolicy()

    def chat_completions(
        self,
        model: str,
        messages: Iterable[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": list(messages),
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if stop:
            payload["stop"] = stop
        if extra:
            payload.update(extra)

        return self._post_json("/v1/chat/completions", payload)

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        last_error: Exception | None = None
        for attempt in range(self._retry.max_retries + 1):
            try:
                request = urllib.request.Request(url, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(request, timeout=self._retry.timeout_s) as response:
                    data = response.read().decode("utf-8")
                return json.loads(data)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
                last_error = exc
                if attempt >= self._retry.max_retries:
                    break
                time.sleep(self._retry.backoff_s)
        raise RuntimeError(f"vLLM chat.completions failed after retries: {last_error}")
