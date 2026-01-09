from __future__ import annotations

from typing import Any

from app.rlm.adapters.repos_sql import RlmRepoSQL


def create_minimal_run(
    repo: RlmRepoSQL,
    session_id: str,
    query: str,
    options: dict[str, Any] | None = None,
) -> str:
    return repo.insert_run(session_id=session_id, query=query, options=options, candidate_index={})
