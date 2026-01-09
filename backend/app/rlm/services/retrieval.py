from __future__ import annotations

from typing import Any

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
    )

    return repo.list_candidates(session_id=session_id, query=query, opt=opt)

