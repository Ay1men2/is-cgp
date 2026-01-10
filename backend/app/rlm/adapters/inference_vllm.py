from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping

from app.rlm.adapters.inference_adapter import InferenceAdapter


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


class InferenceVllmAdapter(InferenceAdapter):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        default_model: str | None = None,
        default_max_tokens: int | None = None,
        default_temperature: float | None = None,
        default_stop: list[str] | None = None,
        default_extra: dict[str, Any] | None = None,
        retry: RetryPolicy | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._retry = retry or RetryPolicy()
        self._client = VllmChatCompletionsClient(
            self._base_url,
            api_key=self._api_key,
            retry=self._retry,
        )
        self._default_model = default_model
        self._default_max_tokens = default_max_tokens
        self._default_temperature = default_temperature
        self._default_stop = default_stop
        self._default_extra = default_extra or {}

    def generate(
        self,
        prompt: str,
        timeout_s: float | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        opts = options or {}
        model = opts.get("model") or self._default_model
        if not model:
            raise ValueError("vLLM model is required for inference.")

        max_tokens = opts.get("max_tokens", self._default_max_tokens)
        temperature = opts.get("temperature", self._default_temperature)
        stop = opts.get("stop") or self._default_stop
        extra = {**self._default_extra, **(opts.get("extra") or {})}
        messages = [{"role": "user", "content": prompt}]

        client = self._client
        if timeout_s is not None:
            override_retry = replace(self._retry, timeout_s=timeout_s)
            client = VllmChatCompletionsClient(
                self._base_url,
                api_key=self._api_key,
                retry=override_retry,
            )

        response = client.chat_completions(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
            extra=extra,
        )
        return _extract_vllm_content(response)


def _extract_vllm_content(response: Mapping[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise RuntimeError("vLLM response missing choices.")

    first = choices[0] or {}
    message = first.get("message") or {}
    content = message.get("content")
    if content is None:
        content = first.get("text")
    if content is None:
        raise RuntimeError("vLLM response missing content.")
    return str(content).strip()
