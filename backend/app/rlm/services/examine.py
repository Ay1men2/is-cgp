from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from app.rlm.adapters.cache import get_glimpse, make_glimpse_key, set_glimpse
from app.rlm.adapters.repos_sql import ArtifactRepo


def _clamp_int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        number = int(value)
    except Exception:
        return default
    if number < lo:
        return lo
    if number > hi:
        return hi
    return number


def _build_spec(mode: str, options: Mapping[str, Any]) -> dict[str, Any]:
    if mode == "range":
        return {
            "mode": mode,
            "start": _clamp_int(options.get("start", 0), default=0, lo=0, hi=10_000_000),
            "end": _clamp_int(options.get("end", 0), default=0, lo=0, hi=10_000_000),
        }
    if mode == "grep":
        return {
            "mode": mode,
            "pattern": str(options.get("pattern", "")),
            "max_lines": _clamp_int(options.get("max_lines", 20), default=20, lo=1, hi=200),
        }
    return {
        "mode": "head",
        "head_chars": _clamp_int(options.get("head_chars", 800), default=800, lo=1, hi=50_000),
    }


def _extract_head(content: str, head_chars: int) -> tuple[str, dict[str, Any]]:
    text = content[:head_chars]
    meta = {
        "mode": "head",
        "head_chars": head_chars,
        "text_length": len(text),
    }
    return text, meta


def _extract_range(content: str, start: int, end: int) -> tuple[str, dict[str, Any]]:
    if end and end < start:
        start, end = end, start
    text = content[start:end] if end else content[start:]
    meta = {
        "mode": "range",
        "start": start,
        "end": end,
        "text_length": len(text),
    }
    return text, meta


def _extract_grep(content: str, pattern: str, max_lines: int) -> tuple[str, dict[str, Any]]:
    matches: list[str] = []
    if pattern:
        for idx, line in enumerate(content.splitlines()):
            if pattern in line:
                matches.append(f"{idx + 1}:{line}")
            if len(matches) >= max_lines:
                break
    text = "\n".join(matches)
    meta = {
        "mode": "grep",
        "pattern": pattern,
        "matches": len(matches),
        "max_lines": max_lines,
    }
    return text, meta


def _extract_glimpse(content: str, spec: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    mode = spec.get("mode", "head")
    if mode == "range":
        return _extract_range(
            content,
            start=int(spec.get("start", 0)),
            end=int(spec.get("end", 0)),
        )
    if mode == "grep":
        return _extract_grep(
            content,
            pattern=str(spec.get("pattern", "")),
            max_lines=int(spec.get("max_lines", 20)),
        )
    return _extract_head(content, head_chars=int(spec.get("head_chars", 800)))


def _make_glimpse_id(artifact_id: str, content_hash: str, spec: Mapping[str, Any]) -> str:
    payload = json.dumps(
        {"artifact_id": artifact_id, "content_hash": content_hash, "spec": dict(spec)},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def examine_artifact(
    repo: ArtifactRepo,
    redis_client: Any,
    artifact_id: str,
    options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    options = options or {}
    mode = str(options.get("mode", "head"))
    spec = _build_spec(mode, options)
    preview_chars = _clamp_int(options.get("preview_chars", 240), default=240, lo=1, hi=2000)
    run_id = str(options.get("run_id") or "unknown")
    glimpse_id = str(
        options.get("glimpse_id")
        or _make_glimpse_id(artifact_id, str(options.get("content_hash") or ""), spec)
    )

    content_hash = options.get("content_hash")
    glimpse_key = None
    if content_hash:
        glimpse_key = make_glimpse_key(run_id, glimpse_id)
        cached = get_glimpse(redis_client, glimpse_key)
    else:
        cached = None

    if cached:
        glimpse_meta = cached.get("meta", {})
        glimpse_text = cached.get("text", "")
    else:
        record = repo.get_content(artifact_id)
        content = record["content"]
        content_hash = record["content_hash"]
        glimpse_id = str(options.get("glimpse_id") or _make_glimpse_id(artifact_id, content_hash, spec))
        glimpse_key = make_glimpse_key(run_id, glimpse_id)

        cached = get_glimpse(redis_client, glimpse_key)
        if cached:
            glimpse_meta = cached.get("meta", {})
            glimpse_text = cached.get("text", "")
        else:
            glimpse_text, meta = _extract_glimpse(content, spec)
            glimpse_meta = {
                **meta,
                "artifact_id": artifact_id,
                "content_hash": content_hash,
            }
            set_glimpse(redis_client, glimpse_key, {"meta": glimpse_meta, "text": glimpse_text})

    glimpse_preview = glimpse_text[:preview_chars]
    include_text = bool(options.get("include_text", False))
    payload: dict[str, Any] = {
        "redis_key": glimpse_key,
        "glimpse_id": glimpse_id,
        "glimpse_meta": glimpse_meta,
        "glimpse_preview": glimpse_preview,
        "glimpse_hash": content_hash,
    }
    if include_text:
        payload["glimpse_text"] = glimpse_text
    return payload
