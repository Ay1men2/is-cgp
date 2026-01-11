from __future__ import annotations

"""
Pipeline executor for RLM program steps.

Program schema (minimal):
{
  "steps": [
    {"action": "select", "selected_ids": ["a1", "a2"], "store": "selected"},
    {"action": "glimpse", "artifact_id": "a1", "mode": "head", "n": 400, "store": "g1"},
    {"action": "glimpse", "artifact_id": "a1", "mode": "range", "start": 0, "end": 200},
    {"action": "glimpse", "artifact_id": "a1", "mode": "grep", "pattern": "foo", "window": 120, "max_hits": 3},
    {"action": "repl", "code": "x = 1\nprint(x)", "timeout_s": 1.0, "store": "repl_vars"},
    {"action": "noop"}
  ]
}

Event schema:
{"step": 1, "action": "glimpse", "status": "ok"|"error", "error": "...", "payload": {...}}

Glimpse schema:
{
  "artifact_id": "a1",
  "mode": "head"|"range"|"grep",
  "text": "excerpt...",
  "span": {"start": 0, "end": 120} | {"spans": [{"start": 10, "end": 80}]},
  "hash": "sha256",
  "glimpse_meta": {"step": 2, "source": "pipeline_executor", "rank": 1, "score": 1.2}
}
"""

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, TYPE_CHECKING

if TYPE_CHECKING:
    from app.rlm.domain.models import CandidateIndex


@dataclass(frozen=True)
class PipelineExecutorLimits:
    max_steps: int = 32
    max_event_errors: int = 3
    max_glimpse_chars: int = 2000
    max_grep_hits: int = 5


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _pick_candidate_text(candidate: Any) -> str | None:
    if candidate is None:
        return None
    if isinstance(candidate, Mapping):
        for key in ("text", "content", "body", "content_preview"):
            value = candidate.get(key)
            if isinstance(value, str) and value:
                return value
        payload = candidate.get("payload")
        if isinstance(payload, Mapping):
            for key in ("text", "content", "body", "content_preview"):
                value = payload.get(key)
                if isinstance(value, str) and value:
                    return value
    for key in ("text", "content", "body", "content_preview"):
        value = getattr(candidate, key, None)
        if isinstance(value, str) and value:
            return value
    payload = getattr(candidate, "payload", None)
    if isinstance(payload, Mapping):
        for key in ("text", "content", "body", "content_preview"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _extract_text_from_record(record: Any) -> str | None:
    if record is None:
        return None
    if isinstance(record, Mapping):
        for key in ("content", "text", "body"):
            value = record.get(key)
            if isinstance(value, str) and value:
                return value
        payload = record.get("payload")
        if isinstance(payload, Mapping):
            for key in ("content", "text", "body"):
                value = payload.get(key)
                if isinstance(value, str) and value:
                    return value
    for key in ("content", "text", "body"):
        value = getattr(record, key, None)
        if isinstance(value, str) and value:
            return value
    payload = getattr(record, "payload", None)
    if isinstance(payload, Mapping):
        for key in ("content", "text", "body"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _call_repo(repo: Any, artifact_id: str) -> tuple[str | None, dict[str, Any] | None]:
    if repo is None:
        return None, None
    targets = [repo]
    for attr in ("artifact_repo", "artifacts", "artifact_repository"):
        if hasattr(repo, attr):
            targets.append(getattr(repo, attr))
    methods = (
        "get_content",
        "get_artifact",
        "get_artifact_content",
        "get_artifact_text",
        "fetch_artifact",
        "fetch_artifact_content",
    )
    last_error: Exception | None = None
    for target in targets:
        for name in methods:
            method = getattr(target, name, None)
            if not callable(method):
                continue
            try:
                record = method(artifact_id)
            except Exception as exc:  # noqa: BLE001 - best-effort discovery
                last_error = exc
                continue
            text = _extract_text_from_record(record)
            if text:
                return text, record if isinstance(record, Mapping) else None
    if last_error is not None:
        raise last_error
    return None, None


def _extract_head(text: str, n: int) -> tuple[str, dict[str, Any]]:
    excerpt = text[:n]
    meta = {"mode": "head", "start": 0, "end": len(excerpt)}
    return excerpt, meta


def _extract_range(text: str, start: int, end: int) -> tuple[str, dict[str, Any]]:
    if start < 0:
        start = 0
    if end <= 0 or end > len(text):
        end = len(text)
    if end < start:
        start, end = end, start
    excerpt = text[start:end]
    meta = {"mode": "range", "start": start, "end": end}
    return excerpt, meta


def _extract_grep(text: str, pattern: str, window: int, max_hits: int) -> tuple[str, dict[str, Any]]:
    if not pattern:
        return "", {"mode": "grep", "pattern": pattern, "matches": 0}
    spans: list[tuple[int, int]] = []
    cursor = 0
    while len(spans) < max_hits:
        idx = text.find(pattern, cursor)
        if idx < 0:
            break
        start = max(0, idx - window)
        end = min(len(text), idx + len(pattern) + window)
        spans.append((start, end))
        cursor = idx + len(pattern)
    excerpts = [text[start:end] for start, end in spans]
    merged = "\n...\n".join(excerpts)
    meta = {
        "mode": "grep",
        "pattern": pattern,
        "matches": len(spans),
        "window": window,
        "spans": [{"start": start, "end": end} for start, end in spans],
    }
    return merged, meta


class PipelineExecutor:
    def __init__(
        self,
        repo: Any | None = None,
        repl_env: Any | None = None,
        *,
        limits: PipelineExecutorLimits | None = None,
    ) -> None:
        self._repo = repo
        self._repl_env = repl_env
        self._limits = limits or PipelineExecutorLimits()

    def execute(self, program: dict[str, Any], index: Any, options: dict[str, Any]) -> dict[str, Any]:
        steps = self._extract_steps(program)
        events: list[dict[str, Any]] = []
        glimpses: list[dict[str, Any]] = []
        subcalls: list[dict[str, Any]] = []
        variables: dict[str, Any] = dict(options.get("vars") or {})
        status = "ok"
        error_count = 0
        stopped = False

        candidates = getattr(index, "candidates", []) if index is not None else []
        candidate_map = {getattr(c, "artifact_id", None): c for c in candidates}

        for step_index, step in enumerate(steps, start=1):
            if step_index > self._limits.max_steps:
                events.append(
                    {
                        "step": step_index,
                        "action": "limit",
                        "status": "error",
                        "error": f"max_steps exceeded: {self._limits.max_steps}",
                    }
                )
                status = "error"
                stopped = True
                break

            action = str(step.get("action", "noop")).strip().lower()
            try:
                if action == "noop":
                    events.append({"step": step_index, "action": action, "status": "ok"})
                    continue

                if action == "select":
                    selected_ids = step.get("selected_ids")
                    if not isinstance(selected_ids, list):
                        raise ValueError("select requires selected_ids list")
                    merged: list[str] = []
                    existing = variables.get("selected_ids")
                    if isinstance(existing, list):
                        merged.extend([item for item in existing if isinstance(item, str)])
                    for item in selected_ids:
                        if not isinstance(item, str) or not item:
                            raise ValueError("select requires non-empty string ids")
                        if item not in merged:
                            merged.append(item)
                    variables["selected_ids"] = merged
                    if step.get("store"):
                        variables[str(step["store"])] = list(merged)
                    events.append({"step": step_index, "action": action, "status": "ok"})
                    continue

                if action == "glimpse":
                    artifact_id = step.get("artifact_id")
                    if not artifact_id:
                        raise ValueError("glimpse requires artifact_id")
                    candidate = candidate_map.get(artifact_id)
                    text: str | None = None
                    record_meta: dict[str, Any] | None = None
                    if self._repo and hasattr(self._repo, "get_artifact_text"):
                        text = self._repo.get_artifact_text(artifact_id)
                        if hasattr(self._repo, "get_artifact_metadata"):
                            record_meta = self._repo.get_artifact_metadata(artifact_id) or None
                    else:
                        text, record = _call_repo(self._repo, artifact_id)
                        if isinstance(record, Mapping):
                            record_meta = dict(record)
                    if text is None:
                        text = _pick_candidate_text(candidate)
                    if not text:
                        raise ValueError(f"glimpse text not found for artifact_id={artifact_id}")

                    mode = str(step.get("mode", "head")).lower()
                    if mode == "range":
                        start = _safe_int(step.get("start"), 0)
                        end = _safe_int(step.get("end"), 0)
                        excerpt, meta = _extract_range(text, start, end)
                    elif mode == "grep":
                        window = _safe_int(step.get("window"), 120)
                        max_hits = _safe_int(step.get("max_hits"), self._limits.max_grep_hits)
                        excerpt, meta = _extract_grep(text, str(step.get("pattern", "")), window, max_hits)
                    else:
                        n = _safe_int(step.get("n"), 0)
                        if not n:
                            n = _safe_int(step.get("head_chars"), self._limits.max_glimpse_chars)
                        excerpt, meta = _extract_head(text, min(n, self._limits.max_glimpse_chars))
                        mode = "head"

                    if not excerpt:
                        raise ValueError("glimpse extracted empty text")

                    glimpse_meta: dict[str, Any] = {
                        "step": step_index,
                        "source": "pipeline_executor",
                        "artifact_id": artifact_id,
                    }
                    if candidate is not None:
                        rank = candidates.index(candidate) + 1 if candidate in candidates else None
                        score = getattr(candidate, "base_score", None)
                        if rank:
                            glimpse_meta["rank"] = rank
                        if score is not None:
                            glimpse_meta["score"] = score
                    if isinstance(record_meta, Mapping):
                        content_hash = record_meta.get("content_hash")
                        if content_hash:
                            glimpse_meta["content_hash"] = content_hash

                    glimpse = {
                        "artifact_id": artifact_id,
                        "mode": mode,
                        "text": excerpt,
                        "span": meta.get("spans") or {"start": meta.get("start"), "end": meta.get("end")},
                        "hash": _sha256(excerpt),
                        "glimpse_meta": glimpse_meta,
                    }
                    glimpses.append(glimpse)
                    if step.get("store"):
                        variables[str(step["store"])] = excerpt
                    events.append({"step": step_index, "action": action, "status": "ok"})
                    continue

                if action == "repl":
                    if not self._repl_env or not hasattr(self._repl_env, "run"):
                        raise ValueError("repl_env_unavailable")
                    code = str(step.get("code") or "")
                    timeout_s = float(step.get("timeout_s") or 1.0)
                    result = self._repl_env.run(code, timeout_s=timeout_s, input_vars=variables)
                    payload = {
                        "stdout": getattr(result, "stdout", ""),
                        "stderr": getattr(result, "stderr", ""),
                        "exception": getattr(result, "exception", None),
                        "duration_ms": getattr(result, "duration_ms", None),
                    }
                    repl_vars = getattr(result, "vars", None)
                    if isinstance(repl_vars, Mapping):
                        variables.update(repl_vars)
                    if step.get("store"):
                        variables[str(step["store"])] = repl_vars if repl_vars is not None else {}
                    events.append(
                        {"step": step_index, "action": action, "status": "ok", "payload": payload}
                    )
                    continue

                raise ValueError(f"unsupported action: {action}")
            except Exception as exc:  # noqa: BLE001 - per-step error handling
                error_count += 1
                status = "error"
                events.append(
                    {"step": step_index, "action": action, "status": "error", "error": str(exc)}
                )
                if error_count > self._limits.max_event_errors:
                    stopped = True
                    break

        meta = {
            "mode": "pipeline_executor",
            "step_count": len(events),
            "error_count": error_count,
            "stopped": stopped,
        }
        return {
            "events": events,
            "glimpses": glimpses,
            "subcalls": subcalls,
            "variables": variables,
            "status": status,
            "meta": meta,
        }

    @staticmethod
    def _extract_steps(program: Any) -> list[dict[str, Any]]:
        if program is None:
            return []
        if isinstance(program, list):
            return [step for step in program if isinstance(step, dict)]
        if isinstance(program, Mapping):
            steps = program.get("steps")
            if isinstance(steps, list):
                return [step for step in steps if isinstance(step, dict)]
            return [program]
        return []
