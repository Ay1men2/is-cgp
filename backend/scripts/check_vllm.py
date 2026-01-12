#!/usr/bin/env python3
"""
Connectivity self-check for a vLLM deployment (OpenAI-compatible).

Checks:
1) GET /v1/models
2) POST /v1/chat/completions
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Optional


def _get_env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value:
        value = value.strip()
    return value or None


def _parse_timeout(value: Optional[str], default: float) -> float:
    if not value:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_base_url(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if not trimmed.endswith("/v1"):
        trimmed = f"{trimmed}/v1"
    return trimmed


def _request_json(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_s: float = 10.0,
) -> dict[str, Any]:
    payload = None
    request_headers = dict(headers or {})
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=payload, headers=request_headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def _extract_model_ids(payload: dict[str, Any]) -> list[str]:
    models = payload.get("data") or payload.get("models") or []
    if not isinstance(models, list):
        raise ValueError("unexpected /v1/models response shape")
    ids: list[str] = []
    for item in models:
        if isinstance(item, dict):
            value = item.get("id") or item.get("model")
        else:
            value = str(item)
        if value:
            ids.append(str(value))
    if not ids:
        raise ValueError("no models returned from /v1/models")
    return ids


def _extract_completion_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise ValueError("vLLM response missing choices")
    first = choices[0] or {}
    message = first.get("message") or {}
    content = message.get("content")
    if content is None:
        content = first.get("text")
    if content is None:
        raise ValueError("vLLM response missing content")
    return str(content).strip()


def _preview_text(text: str, limit: int = 120) -> str:
    cleaned = text.replace("\n", " ").strip()
    if len(cleaned) > limit:
        return f"{cleaned[:limit]}..."
    return cleaned


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check connectivity to a vLLM server")
    parser.add_argument("--base-url", help="Base URL of the vLLM server")
    parser.add_argument("--model", help="Model name for chat completion request")
    parser.add_argument("--timeout-s", help="Timeout in seconds for requests")
    args = parser.parse_args(argv)

    base_url = _get_env("VLLM_BASE_URL") or args.base_url
    api_key = _get_env("VLLM_API_KEY")
    model = _get_env("VLLM_MODEL") or args.model
    timeout_s = _parse_timeout(_get_env("VLLM_TIMEOUT_S") or args.timeout_s, default=20.0)

    if not base_url:
        print("Error: VLLM_BASE_URL must be set", file=sys.stderr)
        return 1

    base_url = _normalize_base_url(base_url)
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        models_payload = _request_json(f"{base_url}/models", headers=headers, timeout_s=timeout_s)
        model_ids = _extract_model_ids(models_payload)
        if not model:
            model = model_ids[0]

        completion_payload = _request_json(
            f"{base_url}/chat/completions",
            method="POST",
            headers=headers,
            timeout_s=timeout_s,
            body={
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 16,
                "temperature": 0.0,
            },
        )
        completion = _extract_completion_text(completion_payload)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
        print(f"Error: vLLM connectivity check failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"Error: unexpected failure: {exc}", file=sys.stderr)
        return 3

    snippet = ", ".join(model_ids[:3])
    print(f"OK models: {snippet}")
    print(f"OK completion: {_preview_text(completion)}")
    print(f"OK base_url: {base_url} model: {model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
