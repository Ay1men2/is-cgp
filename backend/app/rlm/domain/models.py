from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class Candidate(BaseModel):
    artifact_id: str
    scope: str
    type: str
    title: Optional[str] = None
    content_hash: str

    pinned: bool = False
    weight: float = 1.0
    source: str = "manual"

    # 只放 preview，不放全文
    content_preview: str = ""
    content_hash: Optional[str] = None
    token_estimate: Optional[int] = None

    # retrieval 解释字段（确定性，可用于 debug）
    base_score: float = 0.0
    score_breakdown: dict[str, Any] = Field(default_factory=dict)


class CandidateIndex(BaseModel):
    session_id: str
    project_id: str
    query: str
    candidates: list[Candidate]
