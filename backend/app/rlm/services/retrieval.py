from __future__ import annotations

import re
from typing import Any, Iterable

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


_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_WORD_PATTERN = re.compile(r"[A-Za-z0-9_]+")
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]+")


def _iter_word_tokens(query: str) -> Iterable[str]:
    for token in _WORD_PATTERN.findall(query):
        parts = token.split("_")
        for part in parts:
            if not part:
                continue
            for seg in _CAMEL_BOUNDARY.split(part):
                if seg:
                    yield seg


def _iter_cjk_tokens(query: str) -> Iterable[str]:
    for match in _CJK_PATTERN.findall(query):
        if len(match) <= 2:
            yield match
            continue
        for i in range(len(match) - 1):
            yield match[i : i + 2]


def _build_tokens(query: str, max_tokens: int = 12) -> list[str]:
    tokens: list[str] = []
    for token in _iter_word_tokens(query):
        if token:
            tokens.append(token)
            if len(tokens) >= max_tokens:
                return tokens

    if len(tokens) < max_tokens:
        for token in _iter_cjk_tokens(query):
            tokens.append(token)
            if len(tokens) >= max_tokens:
                break

    if not tokens:
        tokens = [query.strip()] if query.strip() else []
    return tokens[:max_tokens]


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

    allowed_types = list(options.get("allowed_types") or [])
    if not allowed_types:
        allowed_types = ["doc", "code", "note"]

    opt = RetrievalOptions(
        include_global=bool(options.get("include_global", True)),
        top_k=_clamp_int(options.get("top_k", 20), default=20, lo=1, hi=200),
        preview_chars=_clamp_int(options.get("preview_chars", 240), default=240, lo=0, hi=4000),
        allowed_types=allowed_types,
    )

    tokens = _build_tokens(query)
    if not tokens:
        tokens = [query]

    return repo.list_candidates(session_id=session_id, query=query, opt=opt, tokens=tokens)
