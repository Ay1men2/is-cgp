from __future__ import annotations

import importlib.util
from pathlib import Path

from app.rlm.services.trace_logger import TraceLogger


def _load_replay_module() -> object:
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "replay_rlm_run.py"
    spec = importlib.util.spec_from_file_location("replay_rlm_run", script_path)
    if not spec or not spec.loader:
        raise RuntimeError("failed_to_load_replay_module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_trace_logger_and_replay(tmp_path, capsys) -> None:
    logger = TraceLogger("run-1", trace_dir=tmp_path)
    logger.append(stage="plan", payload={"steps_count": 1, "candidate_ids_count": 2})
    logger.append(stage="examine", payload={"events_count": 2, "glimpses_count": 1})
    logger.append(stage="decision", payload={"final_answer_preview": "ok", "citations_count": 0})

    module = _load_replay_module()
    exit_code = module._replay(tmp_path / "run-1.jsonl")

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "plan steps=1" in captured.out
    assert "examine events=2" in captured.out
    assert "decision answer=ok" in captured.out
