from __future__ import annotations

import hashlib

from app.rlm.domain.models import Candidate, CandidateIndex
from app.rlm.services.pipeline_executor import PipelineExecutor


class _FakeRepo:
    def __init__(self, text: str) -> None:
        self._text = text

    def get_artifact_text(self, artifact_id: str) -> str | None:
        if artifact_id == "a1":
            return self._text
        return None

    def get_artifact_metadata(self, artifact_id: str) -> dict:
        if artifact_id == "a1":
            return {"content_hash": "hash-a1"}
        return {}


def test_pipeline_executor_glimpse_returns_text() -> None:
    repo = _FakeRepo("Hello from artifact a1.")
    index = CandidateIndex(
        session_id="s1",
        project_id="p1",
        query="q1",
        candidates=[
            Candidate(
                artifact_id="a1",
                scope="session",
                type="note",
                title="t1",
                content_hash="hash-a1",
                content_preview="preview",
                base_score=1.0,
            )
        ],
    )
    program = {"steps": [{"action": "glimpse", "artifact_id": "a1", "mode": "head", "n": 20}]}

    result = PipelineExecutor(repo=repo).execute(program, index, {})

    assert result["status"] == "ok"
    assert result["glimpses"]
    glimpse = result["glimpses"][0]
    assert glimpse["text"]
    assert glimpse["hash"] == hashlib.sha256(glimpse["text"].encode("utf-8")).hexdigest()
