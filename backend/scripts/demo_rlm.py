#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

from sqlalchemy import text

from app.deps import get_engine


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
        text(
            "insert into sessions (project_id) values (:project_id) returning id::text as id"
        ),
        {"project_id": project_id},
    ).mappings().one()
    return row["id"]


def _insert_artifacts(conn, project_id: str, session_id: str) -> list[str]:
    now = datetime.now(timezone.utc).isoformat()
    artifacts = [
        {
            "scope": "global",
            "type": "note",
            "title": "Global onboarding",
            "content": "All projects share the same onboarding checklist.",
            "source": "demo",
            "session_id": None,
        },
        {
            "scope": "project",
            "type": "doc",
            "title": "Project vision",
            "content": "The vision is to build a concise RLM demo workflow.",
            "source": "demo",
            "session_id": None,
        },
        {
            "scope": "session",
            "type": "note",
            "title": "Session notes",
            "content": "Current session focuses on assembling context for a query.",
            "source": "demo",
            "session_id": session_id,
        },
    ]

    inserted_ids: list[str] = []
    for artifact in artifacts:
        content = artifact["content"]
        row = conn.execute(
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
                    :scope,
                    :type,
                    :title,
                    :content,
                    :content_hash,
                    :token_estimate,
                    :metadata::jsonb,
                    :source,
                    'active',
                    :created_at,
                    :updated_at
                )
                returning id::text as id
                """
            ),
            {
                "project_id": project_id,
                "session_id": artifact["session_id"],
                "scope": artifact["scope"],
                "type": artifact["type"],
                "title": artifact["title"],
                "content": content,
                "content_hash": _hash_content(content),
                "token_estimate": _estimate_tokens(content),
                "metadata": json.dumps({"demo_inserted": True}),
                "source": artifact["source"],
                "created_at": now,
                "updated_at": now,
            },
        ).mappings().one()
        inserted_ids.append(row["id"])

    return inserted_ids


def _call_assemble(base_url: str, session_id: str, query: str) -> dict:
    payload = {"session_id": session_id, "query": query, "options": {}}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/rlm/assemble",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Demo RLM assemble flow")
    parser.add_argument("--project", default="demo-rlm", help="project name")
    parser.add_argument("--query", default="What is this session about?", help="query text")
    parser.add_argument(
        "--base-url",
        default=os.getenv("RLM_BASE_URL", "http://localhost:8000"),
        help="API base URL",
    )
    args = parser.parse_args()

    engine = get_engine()
    with engine.begin() as conn:
        project_id = _get_or_create_project_id(conn, args.project)
        session_id = _create_session(conn, project_id)
        artifact_ids = _insert_artifacts(conn, project_id, session_id)

    print(f"Inserted artifacts: {', '.join(artifact_ids)}")
    print(f"Session ID: {session_id}")

    try:
        resp = _call_assemble(args.base_url, session_id, args.query)
    except Exception as exc:  # noqa: BLE001 - demo script should surface error
        print(f"Failed to call assemble API: {exc}", file=sys.stderr)
        return 1

    print("Assemble response summary:")
    print(f"  run_id: {resp.get('run_id')}")
    print(f"  status: {resp.get('status')}")
    print(f"  assembled_context keys: {list((resp.get('assembled_context') or {}).keys())}")
    print(f"  rounds_summary: {resp.get('rounds_summary')}")
    print(f"  rendered_prompt: {resp.get('rendered_prompt')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
