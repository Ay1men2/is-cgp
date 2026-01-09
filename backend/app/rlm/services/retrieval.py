from __future__ import annotations

from typing import Any

import re

from app.rlm.adapters.repos_sql import RetrievalOptions, RlmRepoSQL
from app.rlm.domain.models import CandidateIndex


def _clamp_int(v: Any, default: int, lo: int, hi: int) -> int:
    try:
        n = int(v)
    except Exception:
        n = default
    if n < lo:
        return lo
    if n > hi:
        return hi
    return n


def _split_camel(token: str) -> list[str]:
    if not token:
        return []
    parts: list[str] = []
    buf = token[0]
    for ch in token[1:]:
        if buf and buf[-1].islower() and ch.isupper():
            parts.append(buf)
            buf = ch
        else:
            buf += ch
    if buf:
        parts.append(buf)
    return parts


def _tokenize_query(query: str) -> list[str]:
    raw_segments = re.split(r"[\s_]+", query.strip())
    tokens: list[str] = []
    for segment in raw_segments:
        if not segment:
            continue
        tokens.extend([part for part in _split_camel(segment) if part])

    if tokens:
        return tokens

    windows: list[str] = []
    for run in re.findall(r"[\u4e00-\u9fff]+", query):
        for size in (2, 3):
            if len(run) < size:
                continue
            windows.extend(run[i : i + size] for i in range(len(run) - size + 1))
    if windows:
        return windows

    return [query] if query else []


def _normalize_types(raw: Any) -> list[str] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, (list, tuple, set)):
        items = [str(item) for item in raw if str(item).strip()]
    else:
        return None
    return list(dict.fromkeys(item.strip() for item in items if item.strip())) or None


def build_candidate_index(
    repo: RlmRepoSQL,
    session_id: str,
    query: str,
    options: dict[str, Any] | None = None,
) -> CandidateIndex:
    """
    v0：确定性 candidate retrieval（不接 LLM）
    - options: include_global/top_k/preview_chars
    """
    options = options or {}

    opt = RetrievalOptions(
        include_global=bool(options.get("include_global", True)),
        top_k=_clamp_int(options.get("top_k", 20), default=20, lo=1, hi=200),
        preview_chars=_clamp_int(options.get("preview_chars", 240), default=240, lo=0, hi=4000),
        types=_normalize_types(options.get("types")),
    )

    tokens = _tokenize_query(query)
    tokens = tokens[:8]
    if not tokens:
        tokens = [query]

    return repo.list_candidates(session_id=session_id, query=query, tokens=tokens, opt=opt)
