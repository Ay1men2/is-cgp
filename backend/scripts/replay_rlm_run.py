#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


_DEFAULT_TRACE_DIR = Path(__file__).resolve().parents[1] / "var" / "rlm_traces"


def _resolve_trace_dir(trace_dir: str | Path | None = None) -> Path:
    if trace_dir:
        return Path(trace_dir).expanduser()
    env_dir = os.getenv("RLM_TRACE_DIR")
    if env_dir:
        return Path(env_dir).expanduser()
    return _DEFAULT_TRACE_DIR


def _preview_text(value: Any, limit: int = 120) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\n", " ").strip()
    if not text:
        return None
    if len(text) > limit:
        return f"{text[:limit]}..."
    return text


def _summarize_stage(stage: str, payload: Any) -> str:
    if not isinstance(payload, dict):
        return str(payload)
    stage = stage.strip().lower()
    if stage == "plan":
        steps = payload.get("steps_count")
        candidate_ids = payload.get("candidate_ids_count") or payload.get("candidate_count")
        parts = []
        if steps is not None:
            parts.append(f"steps={steps}")
        if candidate_ids is not None:
            parts.append(f"candidate_ids={candidate_ids}")
        return " ".join(parts) if parts else "plan"
    if stage == "examine":
        events = payload.get("events_count")
        glimpses = payload.get("glimpses_count")
        parts = []
        if events is not None:
            parts.append(f"events={events}")
        if glimpses is not None:
            parts.append(f"glimpses={glimpses}")
        return " ".join(parts) if parts else "examine"
    if stage == "decision":
        preview = _preview_text(payload.get("final_answer_preview"))
        citations = payload.get("citations_count")
        parts = []
        if preview is not None:
            parts.append(f"answer={preview}")
        if citations is not None:
            parts.append(f"citations={citations}")
        return " ".join(parts) if parts else "decision"
    if stage == "error":
        error = payload.get("error")
        return f"error={error}" if error is not None else "error"
    return f"keys={','.join(sorted(payload.keys()))}"


def _replay(trace_path: Path) -> int:
    if not trace_path.exists():
        print(f"trace file not found: {trace_path}", file=sys.stderr)
        return 1
    with trace_path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                print(f"line {line_no} parse error: {exc}", file=sys.stderr)
                continue
            ts = data.get("ts", "")
            stage = data.get("stage", "")
            payload = data.get("payload", {})
            summary = _summarize_stage(stage, payload)
            print(f"{ts} {stage} {summary}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay RLM trace JSONL")
    parser.add_argument("--run-id", required=True, help="run id to replay")
    parser.add_argument("--trace-dir", default=None, help="override trace directory")
    args = parser.parse_args()

    trace_dir = _resolve_trace_dir(args.trace_dir)
    trace_path = trace_dir / f"{args.run_id}.jsonl"
    return _replay(trace_path)


if __name__ == "__main__":
    raise SystemExit(main())
