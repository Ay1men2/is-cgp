from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping
import os
import sys
import time

from app.rlm.adapters.inference_adapter import InferenceAdapter


@dataclass(frozen=True)
class RetryPolicy:
    timeout_s: float = 20.0
    max_retries: int = 1
    backoff_s: float = 0.5


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
        debug = os.getenv("VLLM_DEBUG") == "1"
        if debug:
            payload_size = sum(len(str(m.get("content", ""))) for m in payload.get("messages", []))
            msg_lens = [len(str(m.get("content", ""))) for m in payload.get("messages", [])]
            snippets = [
                f"{m.get('role','?')}[{len(str(m.get('content','')))}]: {str(m.get('content',''))[:80].replace(chr(10),' ')}"
                for m in payload.get("messages", [])
            ]
            print(
                f"[vllm] request url={url} timeout_s={self._retry.timeout_s} "
                f"max_tokens={payload.get('max_tokens')} stop={payload.get('stop')} "
                f"temp={payload.get('temperature')} top_p={payload.get('top_p')} "
                f"messages={len(payload.get('messages', []))} lens={msg_lens} total_chars={payload_size}",
                file=sys.stderr,
            )
            for snippet in snippets:
                print(f"[vllm] msg {snippet}", file=sys.stderr)
        for attempt in range(self._retry.max_retries + 1):
            try:
                request = urllib.request.Request(url, data=body, headers=headers, method="POST")
                start = time.perf_counter()
                with urllib.request.urlopen(request, timeout=self._retry.timeout_s) as response:
                    data = response.read().decode("utf-8")
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                parsed = json.loads(data)
                if debug:
                    print(
                        f"[vllm] success latency_ms={elapsed_ms} content_len={len(data)}",
                        file=sys.stderr,
                    )
                return parsed
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
                last_error = exc
                is_timeout = isinstance(exc, TimeoutError) or "timed out" in str(exc).lower()
                if is_timeout:
                    if debug:
                        print(f"[vllm] timeout, no retry (attempt {attempt}) url={url}", file=sys.stderr)
                    break
                if isinstance(exc, urllib.error.HTTPError) and getattr(exc, "code", 0) < 500:
                    if debug:
                        print(f"[vllm] http {exc.code}, no retry url={url}", file=sys.stderr)
                    break
                if attempt >= self._retry.max_retries:
                    break
                if debug:
                    print(f"[vllm] retrying ({attempt+1}) url={url}", file=sys.stderr)
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
        extra.setdefault("stream", False)
        extra.setdefault("top_p", 1)
        messages_override = opts.get("messages")
        if isinstance(messages_override, list):
            messages = messages_override
        else:
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
