from __future__ import annotations

from typing import Any, Iterable

from app.rlm.domain.models import Candidate


_DROP_DECISIONS = {"drop", "reject", "no", "false", "exclude"}


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _decision_include(decision: dict[str, Any]) -> bool:
    if "include" in decision:
        return bool(decision.get("include"))
    action = decision.get("decision") or decision.get("action")
    if isinstance(action, str):
        return action.strip().lower() not in _DROP_DECISIONS
    return True


def aggregate_decisions(decisions: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """
    聚合 decision：按 artifact_id 合并，多轮取最高 score，并保留最新字段。
    """
    aggregated: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        artifact_id = decision.get("artifact_id")
        if not artifact_id:
            continue
        current = dict(aggregated.get(artifact_id, {}))
        incoming_score = _coerce_float(decision.get("score"), default=0.0)
        current_score = _coerce_float(current.get("score"), default=incoming_score)
        current.update(decision)
        current["score"] = max(current_score, incoming_score)
        current["include"] = current.get("include", _decision_include(decision))
        aggregated[artifact_id] = current
    return aggregated


def _sorted_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        entries,
        key=lambda item: (
            1 if item.get("pinned") else 0,
            _coerce_float(item.get("score"), default=0.0),
            _coerce_float(item.get("base_score"), default=0.0),
            _coerce_float(item.get("weight"), default=0.0),
        ),
        reverse=True,
    )


def assemble_decisions(
    candidates: Iterable[Candidate],
    decisions: Iterable[dict[str, Any]],
    *,
    budget: int,
    drop_pinned: bool = False,
    write_suggestions: bool = False,
) -> dict[str, Any]:
    """
    聚合 decision，强制 pinned 进入（除非 drop_pinned），再排序 + truncate。
    """
    aggregated = aggregate_decisions(decisions)

    pinned_entries: list[dict[str, Any]] = []
    ranked_entries: list[dict[str, Any]] = []

    for candidate in candidates:
        decision = aggregated.get(candidate.artifact_id)
        is_pinned = candidate.pinned and not drop_pinned
        if decision is None and not is_pinned:
            continue
        include = is_pinned or _decision_include(decision or {})
        if not include:
            continue

        entry = {
            "artifact_id": candidate.artifact_id,
            "scope": candidate.scope,
            "type": candidate.type,
            "title": candidate.title,
            "pinned": candidate.pinned,
            "weight": candidate.weight,
            "source": candidate.source,
            "content_preview": candidate.content_preview,
            "token_estimate": candidate.token_estimate,
            "base_score": candidate.base_score,
            "decision": decision or {},
            "score": _coerce_float(
                (decision or {}).get("score"),
                default=candidate.base_score,
            ),
        }

        if is_pinned:
            pinned_entries.append(entry)
        else:
            ranked_entries.append(entry)

    pinned_entries = _sorted_entries(pinned_entries)
    ranked_entries = _sorted_entries(ranked_entries)

    if budget < 0:
        budget = 0

    if pinned_entries:
        remaining = max(budget - len(pinned_entries), 0)
    else:
        remaining = budget

    selected = pinned_entries + ranked_entries[:remaining]

    payload: dict[str, Any] = {
        "selected": selected,
        "aggregated": aggregated,
        "budget": budget,
        "drop_pinned": drop_pinned,
    }

    if write_suggestions:
        payload["suggestions"] = _extract_suggestions(decisions)

    return payload


def _extract_suggestions(decisions: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    for decision in decisions:
        for suggestion in _iter_suggestions(decision):
            if suggestion is None:
                continue
            if isinstance(suggestion, str):
                item = {"text": suggestion}
            elif isinstance(suggestion, dict):
                item = dict(suggestion)
            else:
                continue
            item.setdefault("source", "llm_suggestion")
            suggestions.append(item)
    return suggestions


def _iter_suggestions(decision: dict[str, Any]) -> list[Any]:
    raw = decision.get("suggestion")
    if raw is None:
        raw = decision.get("suggestions")
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    return [raw]
