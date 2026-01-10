from __future__ import annotations

import re
import shlex
from typing import Any, Literal, Sequence

from pydantic import BaseModel, Field, TypeAdapter, ValidationError


class ReplLimits(BaseModel):
    max_steps: int = Field(default=64, ge=1, le=1000)
    max_glimpse_chars: int = Field(default=2000, ge=1, le=20_000)
    max_total_glimpse_chars: int = Field(default=20_000, ge=1, le=200_000)
    max_subcalls: int = Field(default=4, ge=0, le=50)
    max_depth: int = Field(default=3, ge=0, le=10)


DEFAULT_LIMITS = ReplLimits()


class BaseCommand(BaseModel):
    type: str


class ListArtifactsCommand(BaseCommand):
    type: Literal["LIST_ARTIFACTS"]
    query: str = Field(min_length=1)
    top_k: int = Field(default=20, ge=1, le=200)
    include_global: bool = True
    allowed_types: list[str] = Field(default_factory=list)
    store: str | None = None


class PeekHeadCommand(BaseCommand):
    type: Literal["PEEK_HEAD"]
    artifact_id: str = Field(min_length=1)
    head_chars: int = Field(default=800, ge=1, le=DEFAULT_LIMITS.max_glimpse_chars)
    content_hash: str | None = None
    store: str | None = None


class PeekRangeCommand(BaseCommand):
    type: Literal["PEEK_RANGE"]
    artifact_id: str = Field(min_length=1)
    start: int = Field(default=0, ge=0, le=10_000_000)
    end: int = Field(default=0, ge=0, le=10_000_000)
    content_hash: str | None = None
    store: str | None = None


class GrepCommand(BaseCommand):
    type: Literal["GREP"]
    artifact_id: str = Field(min_length=1)
    pattern: str = Field(min_length=1)
    max_lines: int = Field(default=20, ge=1, le=200)
    content_hash: str | None = None
    store: str | None = None


class ChunkByNewlineCommand(BaseCommand):
    type: Literal["CHUNK_BY_NEWLINE"]
    source: str = Field(default="last")
    max_lines: int = Field(default=40, ge=1, le=500)
    max_chars: int = Field(default=DEFAULT_LIMITS.max_glimpse_chars, ge=1, le=DEFAULT_LIMITS.max_glimpse_chars)
    store: str | None = None


class SubcallCommand(BaseCommand):
    type: Literal["SUBCALL"]
    prompt: str = Field(min_length=1)
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=4096)
    store: str | None = None


class SubRlmRunCommand(BaseCommand):
    type: Literal["SUBRLM_RUN"]
    prompt: str = Field(min_length=1)
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=4096)
    store: str | None = None


class SetCommand(BaseCommand):
    type: Literal["SET"]
    name: str = Field(min_length=1)
    value: str


class AppendCommand(BaseCommand):
    type: Literal["APPEND"]
    name: str = Field(min_length=1)
    value: str


class FinalCommand(BaseCommand):
    type: Literal["FINAL"]
    name: str = Field(min_length=1)


class FinalTextCommand(BaseCommand):
    type: Literal["FINAL_TEXT"]
    text: str


class StopCommand(BaseCommand):
    type: Literal["STOP"]


Command = (
    ListArtifactsCommand
    | PeekHeadCommand
    | PeekRangeCommand
    | GrepCommand
    | ChunkByNewlineCommand
    | SubcallCommand
    | SubRlmRunCommand
    | SetCommand
    | AppendCommand
    | FinalCommand
    | FinalTextCommand
    | StopCommand
)

_COMMAND_ADAPTER = TypeAdapter(Command)


_FENCE_RE = re.compile(r"```rlm_repl\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_int(value: str) -> int:
    return int(value.strip())


def _parse_float(value: str) -> float:
    return float(value.strip())


def _split_kv(tokens: Sequence[str]) -> tuple[dict[str, str], list[str]]:
    kv: dict[str, str] = {}
    positional: list[str] = []
    for token in tokens:
        if "=" in token:
            key, value = token.split("=", 1)
            kv[key.strip()] = value
        else:
            positional.append(token)
    return kv, positional


def _parse_command_line(line: str) -> dict[str, Any]:
    tokens = shlex.split(line, comments=False, posix=True)
    if not tokens:
        raise ValueError("empty command")
    name = tokens[0].strip().upper()
    kv, positional = _split_kv(tokens[1:])

    def pop_pos(default: str = "") -> str:
        if positional:
            return positional.pop(0)
        return default

    def join_pos() -> str:
        return " ".join(positional).strip()

    data: dict[str, Any] = {"type": name}
    if name == "LIST_ARTIFACTS":
        query = kv.get("query") or join_pos()
        data.update(
            {
                "query": query,
                "top_k": _parse_int(kv["top_k"]) if "top_k" in kv else 20,
                "include_global": _parse_bool(kv["include_global"]) if "include_global" in kv else True,
                "store": kv.get("store"),
            }
        )
        if "allowed_types" in kv:
            data["allowed_types"] = [item for item in kv["allowed_types"].split(",") if item]
        return data

    if name == "PEEK_HEAD":
        data.update(
            {
                "artifact_id": kv.get("artifact_id") or pop_pos(),
                "head_chars": _parse_int(kv["head_chars"]) if "head_chars" in kv else 800,
                "content_hash": kv.get("content_hash"),
                "store": kv.get("store"),
            }
        )
        return data

    if name == "PEEK_RANGE":
        data.update(
            {
                "artifact_id": kv.get("artifact_id") or pop_pos(),
                "start": _parse_int(kv["start"]) if "start" in kv else 0,
                "end": _parse_int(kv["end"]) if "end" in kv else 0,
                "content_hash": kv.get("content_hash"),
                "store": kv.get("store"),
            }
        )
        return data

    if name == "GREP":
        data.update(
            {
                "artifact_id": kv.get("artifact_id") or pop_pos(),
                "pattern": kv.get("pattern") or join_pos(),
                "max_lines": _parse_int(kv["max_lines"]) if "max_lines" in kv else 20,
                "content_hash": kv.get("content_hash"),
                "store": kv.get("store"),
            }
        )
        return data

    if name == "CHUNK_BY_NEWLINE":
        data.update(
            {
                "source": kv.get("source") or pop_pos() or "last",
                "max_lines": _parse_int(kv["max_lines"]) if "max_lines" in kv else 40,
                "max_chars": _parse_int(kv["max_chars"])
                if "max_chars" in kv
                else DEFAULT_LIMITS.max_glimpse_chars,
                "store": kv.get("store"),
            }
        )
        return data

    if name in {"SUBCALL", "SUBRLM_RUN"}:
        prompt = kv.get("prompt") or join_pos()
        data.update(
            {
                "prompt": prompt,
                "model": kv.get("model"),
                "temperature": _parse_float(kv["temperature"]) if "temperature" in kv else None,
                "max_tokens": _parse_int(kv["max_tokens"]) if "max_tokens" in kv else None,
                "store": kv.get("store"),
            }
        )
        return data

    if name == "SET":
        data.update(
            {
                "name": kv.get("name") or pop_pos(),
                "value": kv.get("value") or join_pos(),
            }
        )
        return data

    if name == "APPEND":
        data.update(
            {
                "name": kv.get("name") or pop_pos(),
                "value": kv.get("value") or join_pos(),
            }
        )
        return data

    if name == "FINAL":
        data.update(
            {
                "name": kv.get("name") or pop_pos(),
            }
        )
        return data

    if name == "FINAL_TEXT":
        data.update(
            {
                "text": kv.get("text") or join_pos(),
            }
        )
        return data

    if name == "STOP":
        return data

    raise ValueError(f"unknown command: {name}")


def _iter_blocks(text: str) -> list[str]:
    blocks = [match.group(1) for match in _FENCE_RE.finditer(text)]
    if blocks:
        return blocks
    return [text]


def parse_program(text: str) -> list[Command]:
    commands: list[Command] = []
    for block in _iter_blocks(text):
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            data = _parse_command_line(line)
            try:
                command = _COMMAND_ADAPTER.validate_python(data)
            except ValidationError as exc:
                raise ValueError(f"invalid command: {line}") from exc
            commands.append(command)

    if len(commands) > DEFAULT_LIMITS.max_steps:
        raise ValueError(f"command count exceeds max_steps={DEFAULT_LIMITS.max_steps}")

    return commands
