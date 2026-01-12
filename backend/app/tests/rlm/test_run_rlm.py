from __future__ import annotations

from typing import Any

from app.rlm.domain.models import Candidate, CandidateIndex
from app.rlm.services.run_pipeline import run_rlm


class _FakeRepo:
    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    def list_candidates(self, session_id: str, query: str, tokens: list[str], opt: Any) -> CandidateIndex:
        candidate = Candidate(
            artifact_id="a1",
            scope="session",
            type="note",
            title="t1",
            content_hash="hash-a1",
            content_preview="preview",
            base_score=1.0,
        )
        return CandidateIndex(
            session_id=session_id,
            project_id="p1",
            query=query,
            candidates=[candidate],
        )

    def insert_run(
        self,
        session_id: str,
        query: str,
        options: dict | None = None,
        candidate_index: dict | None = None,
    ) -> str:
        return "run-1"

    def update_run_payload(
        self,
        run_id: str,
        *,
        program: dict,
        meta: dict,
        events: list[dict],
        glimpses: list[dict],
        glimpses_meta: list[dict],
        subcalls: list[dict],
        evidence: list[dict],
        final: dict,
        final_answer: str | None,
        citations: list[Any],
        status: str,
        errors: list[dict] | dict | None = None,
    ) -> None:
        self.payloads.append(
            {
                "run_id": run_id,
                "status": status,
                "final_answer": final_answer,
                "events": events,
                "glimpses": glimpses,
                "meta": meta,
            }
        )

    def get_artifact_text(self, artifact_id: str) -> str | None:
        if artifact_id == "a1":
            return "Full content for artifact a1."
        return None

    def get_artifact_metadata(self, artifact_id: str) -> dict[str, Any]:
        if artifact_id == "a1":
            return {"content_hash": "hash-a1"}
        return {}


def test_run_rlm_with_real_executor(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RLM_TRACE_DIR", str(tmp_path))
    repo = _FakeRepo()
    result = run_rlm(repo, "s1", "what is this?", {"executor_backend": "real"})

    assert result.status == "ok"
    assert result.final_answer
    assert result.glimpses


def test_run_rlm_decision_vllm_fallback(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RLM_TRACE_DIR", str(tmp_path))
    repo = _FakeRepo()
    options = {
        "executor_backend": "real",
        "rootlm_backend": "vllm",
        "vllm_base_url": "http://127.0.0.1:1/v1",
        "vllm_model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    }
    result = run_rlm(repo, "s1", "what is this?", options)

    steps = result.program.get("steps") if isinstance(result.program, dict) else None
    assert result.status == "ok"
    assert isinstance(steps, list) and len(steps) >= 1
    assert len(result.glimpses) >= 1
    assert result.final_answer
    assert result.final_answer.startswith("Mock answer for:")


def test_run_rlm_decision_vllm_timeout_sets_fallback(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RLM_TRACE_DIR", str(tmp_path))

    class FakeAdapter:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def generate(self, *args, **kwargs) -> str:
            raise TimeoutError("simulated timeout")

    monkeypatch.setattr("app.rlm.services.run_pipeline.InferenceVllmAdapter", FakeAdapter)

    repo = _FakeRepo()
    options = {
        "executor_backend": "real",
        "rootlm_backend": "vllm",
        "vllm_base_url": "http://127.0.0.1:1/v1",
        "vllm_model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    }
    result = run_rlm(repo, "s1", "what is this?", options)

    assert result.status == "ok"
    assert result.final_answer.startswith("Mock answer for:")
    meta = repo.payloads[-1]["meta"]
    assert meta.get("round3", {}).get("fallback_reason")
