from __future__ import annotations

import json
from typing import Any, Mapping

from app.config import settings


def make_glimpse_key(run_id: str, glimpse_id: str) -> str:
    return f"rlm:glimpse:{run_id}:{glimpse_id}"


def make_subcall_key(run_id: str, subcall_id: str) -> str:
    return f"rlm:subcall:{run_id}:{subcall_id}"


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
