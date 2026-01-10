#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import text

from app.deps import get_engine
from app.rlm.adapters.repos_sql import RetrievalOptions, RlmRepoSQL


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _estimate_tokens(content: str) -> int:
    return max(1, len(content.split()))


def _get_or_create_project_id(conn, name: str) -> str:
    row = conn.execute(
        text("select id::text as id from projects where name = :name"),
        {"name": name},
    ).mappings().first()
    if row:
        return row["id"]

    row = conn.execute(
        text("insert into projects (name) values (:name) returning id::text as id"),
        {"name": name},
    ).mappings().one()
    return row["id"]


def _create_session(conn, project_id: str) -> str:
    row = conn.execute(
        text("insert into sessions (project_id) values (:project_id) returning id::text as id"),
        {"project_id": project_id},
    ).mappings().one()
    return row["id"]


def _insert_artifacts(conn, project_id: str, session_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    artifacts = [
        ("doc", "Doc artifact", "This is a doc artifact."),
        ("code", "Code artifact", "print('hello world')"),
        ("note", "Note artifact", "This is a note artifact."),
    ]
    for artifact_type, title, content in artifacts:
        conn.execute(
            text(
                """
                insert into artifacts (
                    project_id,
                    session_id,
                    scope,
                    type,
                    title,
                    content,
                    content_hash,
                    token_estimate,
                    metadata,
                    source,
                    status,
                    created_at,
                    updated_at
                ) values (
                    :project_id,
                    :session_id,
                    'project',
                    :type,
                    :title,
                    :content,
                    :content_hash,
                    :token_estimate,
                    :metadata::jsonb,
                    'test',
                    'active',
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "project_id": project_id,
                "session_id": session_id,
                "type": artifact_type,
                "title": title,
                "content": content,
                "content_hash": _hash_content(content),
                "token_estimate": _estimate_tokens(content),
                "metadata": json.dumps({"test_inserted": True}),
                "created_at": now,
                "updated_at": now,
            },
        )


def main() -> int:
    engine = get_engine()
    repo = RlmRepoSQL(engine)

    with engine.begin() as conn:
        project_id = _get_or_create_project_id(conn, "test-list-candidates")
        session_id = _create_session(conn, project_id)
        _insert_artifacts(conn, project_id, session_id)

    opt = RetrievalOptions(
        include_global=False,
        top_k=10,
        preview_chars=120,
        allowed_types=["doc"],
    )
    candidates = repo.list_candidates(
        session_id=session_id,
        query="doc artifact",
        tokens=["doc"],
        opt=opt,
    )

    types = {candidate.type for candidate in candidates.candidates}
    if types != {"doc"}:
        raise SystemExit(f"expected only doc types, got: {sorted(types)}")

    print("ok: list_candidates allowed_types filter works")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
