from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from app.config import settings


def make_glimpse_key(artifact_id: str, content_hash: str, spec: Mapping[str, Any]) -> str:
    payload = json.dumps(spec, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"rlm:glimpse:{artifact_id}:{content_hash}:{digest}"


def _normalize_ttl(value: int) -> int:
    try:
        ttl = int(value)
    except Exception:
        ttl = 0
    return max(ttl, 0)


def get_glimpse(redis_client: Any, key: str) -> dict[str, Any] | None:
    if redis_client is None:
        return None
    raw = redis_client.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def set_glimpse(redis_client: Any, key: str, payload: Mapping[str, Any]) -> None:
    if redis_client is None:
        return
    ttl = _normalize_ttl(settings.rlm_glimpse_ttl_sec)
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if ttl:
        redis_client.setex(key, ttl, data)
    else:
        redis_client.set(key, data)
