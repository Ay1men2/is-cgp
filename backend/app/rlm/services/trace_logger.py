from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEFAULT_TRACE_DIR = Path(__file__).resolve().parents[3] / "var" / "rlm_traces"


def _jsonable(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(item) for item in obj]
    if is_dataclass(obj):
        return _jsonable(asdict(obj))
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        try:
            return _jsonable(obj.model_dump())
        except Exception:
            return str(obj)
    return str(obj)


def _resolve_trace_dir(trace_dir: str | Path | None = None) -> Path:
    if trace_dir:
        return Path(trace_dir).expanduser()
    env_dir = os.getenv("RLM_TRACE_DIR")
    if env_dir:
        return Path(env_dir).expanduser()
    return _DEFAULT_TRACE_DIR


class TraceLogger:
    def __init__(self, run_id: str, trace_dir: str | Path | None = None) -> None:
        self._run_id = str(run_id)
        self._trace_dir = _resolve_trace_dir(trace_dir)
        self._trace_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._trace_dir / f"{self._run_id}.jsonl"

    @property
    def path(self) -> Path:
        return self._path

    def append(self, *, stage: str, payload: dict, meta: dict | None = None) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": self._run_id,
            "stage": str(stage),
            "payload": _jsonable(payload),
            "meta": _jsonable(meta or {}),
        }
        self._write_line(entry)

    def append_error(self, *, stage: str, error: str, meta: dict | None = None) -> None:
        payload = {"error": str(error)}
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": self._run_id,
            "stage": str(stage),
            "payload": _jsonable(payload),
            "meta": _jsonable(meta or {}),
        }
        self._write_line(entry)

    def _write_line(self, entry: dict[str, Any]) -> None:
        line = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()


def get_trace_logger(run_id: str, trace_dir: str | Path | None = None) -> TraceLogger:
    return TraceLogger(run_id, trace_dir=trace_dir)
