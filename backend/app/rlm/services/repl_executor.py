from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

from app.rlm.adapters.cache import make_glimpse_key
from app.rlm.adapters.repos_sql import ArtifactRepo, RlmRepoSQL
from app.rlm.services.examine import examine_artifact
from app.rlm.services.retrieval import build_candidate_index
from app.rlm.services.repl_parser import (
    AppendCommand,
    ChunkByNewlineCommand,
    Command,
    FinalCommand,
    FinalTextCommand,
    GrepCommand,
    ListArtifactsCommand,
    PeekHeadCommand,
    PeekRangeCommand,
    ReplLimits,
    SetCommand,
    StopCommand,
    SubRlmRunCommand,
    SubcallCommand,
    DEFAULT_LIMITS,
)
from app.rlm.services.runs import create_minimal_run


class InferenceAdapter(Protocol):
    def run(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> str: ...


@dataclass
class ReplContext:
    session_id: str
    run_id: str
    rlm_repo: RlmRepoSQL
    artifact_repo: ArtifactRepo
    redis_client: Any
    inference_adapter: Any


@dataclass
class ExecutionState:
    variables: dict[str, Any] = field(default_factory=dict)
    last_text: str = ""
    final_text: str | None = None
    total_glimpse_chars: int = 0
    subcall_count: int = 0


_VAR_PATTERN = re.compile(r"\$\{([A-Za-z0-9_]+)\}")


def _substitute_vars(text: str, variables: dict[str, Any]) -> str:
    def replacer(match: re.Match[str]) -> str:
        key = match.group(1)
        value = variables.get(key, "")
        return str(value)

    return _VAR_PATTERN.sub(replacer, text)


def _call_inference(adapter: Any, prompt: str, **options: Any) -> str:
    if hasattr(adapter, "run"):
        return adapter.run(prompt=prompt, **options)
    if hasattr(adapter, "chat_completions"):
        model = options.get("model") or "default"
        response = adapter.chat_completions(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=options.get("temperature"),
            max_tokens=options.get("max_tokens"),
        )
        choices = response.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            return str(message.get("content") or "").strip()
        return ""
    if callable(adapter):
        return adapter(prompt=prompt, **options)
    raise RuntimeError("inference adapter is not callable")


def _hash_preview(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunk_by_newline(text: str, max_lines: int, max_chars: int) -> list[str]:
    chunks: list[str] = []
    buffer: list[str] = []
    char_count = 0
    for line in text.splitlines():
        line_len = len(line) + 1
        if buffer and (len(buffer) >= max_lines or char_count + line_len > max_chars):
            chunks.append("\n".join(buffer))
            buffer = []
            char_count = 0
        buffer.append(line)
        char_count += line_len
    if buffer:
        chunks.append("\n".join(buffer))
    return chunks


def _push_event(events: list[dict[str, Any]], seq: int, event_type: str, payload: Any | None, error: str | None) -> None:
    events.append(
        {
            "seq": seq,
            "type": event_type,
            "payload": payload,
            "error": error,
        }
    )


def execute_program(
    program: Iterable[Command],
    *,
    context: ReplContext,
    limits: ReplLimits | None = None,
    depth: int = 0,
) -> dict[str, Any]:
    limits = limits or DEFAULT_LIMITS
    if depth > limits.max_depth:
        raise ValueError(f"execution depth exceeds max_depth={limits.max_depth}")

    events: list[dict[str, Any]] = []
    glimpses: list[dict[str, Any]] = []
    state = ExecutionState()
    seq = 0

    for command in program:
        seq += 1
        if seq > limits.max_steps:
            _push_event(events, seq, "error", None, f"max_steps exceeded: {limits.max_steps}")
            break

        try:
            if isinstance(command, ListArtifactsCommand):
                query = _substitute_vars(command.query, state.variables)
                if not query.strip():
                    _push_event(
                        events,
                        seq,
                        "error",
                        {"command": command.type},
                        "empty_query_not_allowed",
                    )
                    continue
                try:
                    index = build_candidate_index(
                        context.rlm_repo,
                        session_id=context.session_id,
                        query=query,
                        options={
                            "include_global": command.include_global,
                            "top_k": command.top_k,
                            "allowed_types": command.allowed_types,
                        },
                    )
                except Exception as exc:
                    _push_event(
                        events,
                        seq,
                        "error",
                        {"command": command.type, "query": query},
                        str(exc),
                    )
                    continue
                payload = {
                    "query": query,
                    "count": len(index.candidates),
                    "candidates": [item.model_dump() for item in index.candidates],
                }
                if command.store:
                    state.variables[command.store] = payload
                _push_event(events, seq, "list_artifacts", payload, None)
                continue

            if isinstance(command, PeekHeadCommand):
                payload = _handle_glimpse(
                    command,
                    context=context,
                    state=state,
                    limits=limits,
                    mode="head",
                    options={
                        "head_chars": command.head_chars,
                        "content_hash": command.content_hash,
                    },
                )
                _append_glimpse(glimpses, payload)
                if command.store:
                    state.variables[command.store] = payload.get("glimpse_text", "")
                _push_event(events, seq, "peek_head", payload, None)
                continue

            if isinstance(command, PeekRangeCommand):
                payload = _handle_glimpse(
                    command,
                    context=context,
                    state=state,
                    limits=limits,
                    mode="range",
                    options={
                        "start": command.start,
                        "end": command.end,
                        "content_hash": command.content_hash,
                    },
                )
                _append_glimpse(glimpses, payload)
                if command.store:
                    state.variables[command.store] = payload.get("glimpse_text", "")
                _push_event(events, seq, "peek_range", payload, None)
                continue

            if isinstance(command, GrepCommand):
                pattern = _substitute_vars(command.pattern, state.variables)
                payload = _handle_glimpse(
                    command,
                    context=context,
                    state=state,
                    limits=limits,
                    mode="grep",
                    options={
                        "pattern": pattern,
                        "max_lines": command.max_lines,
                        "content_hash": command.content_hash,
                    },
                )
                _append_glimpse(glimpses, payload)
                if command.store:
                    state.variables[command.store] = payload.get("glimpse_text", "")
                _push_event(events, seq, "grep", payload, None)
                continue

            if isinstance(command, ChunkByNewlineCommand):
                source = command.source
                if source == "last":
                    text = state.last_text
                else:
                    text = str(state.variables.get(source, ""))
                chunks = _chunk_by_newline(text, command.max_lines, command.max_chars)
                payload = {
                    "source": source,
                    "chunk_count": len(chunks),
                    "preview": chunks[0][: limits.max_glimpse_chars] if chunks else "",
                }
                if command.store:
                    state.variables[command.store] = chunks
                _push_event(events, seq, "chunk_by_newline", payload, None)
                continue

            if isinstance(command, (SubcallCommand, SubRlmRunCommand)):
                if state.subcall_count >= limits.max_subcalls:
                    _push_event(events, seq, "subcall", None, f"max_subcalls exceeded: {limits.max_subcalls}")
                    continue
                state.subcall_count += 1
                prompt = _substitute_vars(command.prompt, state.variables)
                subcall_id = uuid.uuid4().hex
                child_run_id = None
                if isinstance(command, SubRlmRunCommand):
                    child_run_id = create_minimal_run(
                        context.rlm_repo,
                        context.session_id,
                        prompt,
                        options={"parent_run_id": context.run_id, "subcall_id": subcall_id},
                    )
                output = _call_inference(
                    context.inference_adapter,
                    prompt,
                    model=command.model,
                    temperature=command.temperature,
                    max_tokens=command.max_tokens,
                )
                preview = output[: limits.max_glimpse_chars]
                payload = {
                    "subcall_id": subcall_id,
                    "prompt": prompt,
                    "preview": preview,
                    "length": len(output),
                }
                if child_run_id:
                    payload["child_run_id"] = child_run_id
                    payload["parent_run_id"] = context.run_id
                if command.store:
                    state.variables[command.store] = output
                event_type = "subrlm_run" if isinstance(command, SubRlmRunCommand) else "subcall"
                _push_event(events, seq, event_type, payload, None)
                continue

            if isinstance(command, SetCommand):
                value = _substitute_vars(command.value, state.variables)
                state.variables[command.name] = value
                _push_event(events, seq, "set", {"name": command.name}, None)
                continue

            if isinstance(command, AppendCommand):
                value = _substitute_vars(command.value, state.variables)
                current = state.variables.get(command.name, "")
                state.variables[command.name] = f"{current}{value}"
                _push_event(events, seq, "append", {"name": command.name}, None)
                continue

            if isinstance(command, FinalCommand):
                state.final_text = str(state.variables.get(command.name, ""))
                _push_event(events, seq, "final", {"name": command.name}, None)
                break

            if isinstance(command, FinalTextCommand):
                state.final_text = _substitute_vars(command.text, state.variables)
                _push_event(events, seq, "final_text", {"length": len(state.final_text)}, None)
                break

            if isinstance(command, StopCommand):
                _push_event(events, seq, "stop", None, None)
                break

            _push_event(events, seq, "error", None, f"unsupported command: {command.type}")
        except Exception as exc:
            _push_event(events, seq, "error", None, str(exc))

    return {
        "events": events,
        "glimpses": glimpses,
        "variables": state.variables,
        "final_text": state.final_text,
    }


def _append_glimpse(glimpses: list[dict[str, Any]], payload: dict[str, Any]) -> None:
    glimpse = {
        "preview": payload.get("preview", ""),
        "preview_hash": payload.get("preview_hash", ""),
        "redis_key": payload.get("redis_key") or payload.get("glimpse_key"),
        "artifact_id": (payload.get("glimpse_meta") or {}).get("artifact_id"),
        "content_hash": (payload.get("glimpse_meta") or {}).get("content_hash"),
    }
    glimpses.append(glimpse)


def _handle_glimpse(
    command: PeekHeadCommand | PeekRangeCommand | GrepCommand,
    *,
    context: ReplContext,
    state: ExecutionState,
    limits: ReplLimits,
    mode: str,
    options: dict[str, Any],
) -> dict[str, Any]:
    spec = {"mode": mode, **{k: v for k, v in options.items() if k != "content_hash"}}
    payload = examine_artifact(
        context.artifact_repo,
        context.redis_client,
        command.artifact_id,
        {
            "mode": mode,
            **options,
            "run_id": context.run_id,
            "include_text": True,
        },
    )
    glimpse_text = payload.get("glimpse_text") or ""
    state.last_text = glimpse_text
    state.total_glimpse_chars += len(glimpse_text)
    if state.total_glimpse_chars > limits.max_total_glimpse_chars:
        raise ValueError(f"max_total_glimpse_chars exceeded: {limits.max_total_glimpse_chars}")

    glimpse_id = payload.get("glimpse_id")
    glimpse_key = payload.get("redis_key") or payload.get("glimpse_key")
    if not glimpse_key and glimpse_id:
        glimpse_key = make_glimpse_key(context.run_id, str(glimpse_id))
        payload["glimpse_key"] = glimpse_key

    preview = glimpse_text[: limits.max_glimpse_chars]
    payload["preview"] = preview
    payload["preview_hash"] = _hash_preview(preview)
    payload["preview_chars"] = len(preview)
    if glimpse_key:
        payload["redis_key"] = glimpse_key
    return payload
