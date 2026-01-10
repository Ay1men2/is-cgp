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
from app.rlm.adapters.repos_sql import RlmRepoSQL
from app.rlm.services.rlm_pipeline import RunResult, run_rlm


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
        row = conn.exec_driver_sql(
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
                %(project_id)s,
                %(session_id)s,
                %(scope)s,
                %(type)s,
                %(title)s,
                %(content)s,
                %(content_hash)s,
                %(token_estimate)s,
                COALESCE(%(metadata)s, '{}')::jsonb,
                %(source)s,
                'active',
                %(created_at)s,
                %(updated_at)s
            )
            on conflict do nothing
            returning id::text as id
            """,
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
        ).mappings().first()
        if not row:
            row = conn.execute(
                text(
                    """
                    select id::text as id
                    from artifacts
                    where project_id = :project_id
                      and scope = :scope
                      and type = :type
                      and session_id is not distinct from :session_id
                      and content_hash = :content_hash
                      and status = 'active'
                    limit 1
                    """
                ),
                {
                    "project_id": project_id,
                    "session_id": artifact["session_id"],
                    "scope": artifact["scope"],
                    "type": artifact["type"],
                    "content_hash": _hash_content(content),
                },
            ).mappings().one()
        inserted_ids.append(row["id"])

    return inserted_ids


def _call_run(base_url: str, session_id: str, query: str) -> dict:
    payload = {"session_id": session_id, "query": query, "options": {}}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/rlm/run",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def _direct_run(session_id: str, query: str) -> RunResult:
    engine = get_engine()
    repo = RlmRepoSQL(engine)
    return run_rlm(repo, session_id, query, {})


def _summarize_program(program: dict) -> str:
    if not program:
        return "none"

    summary_parts: list[str] = []
    steps = program.get("steps")
    if isinstance(steps, list):
        summary_parts.append(f"steps={len(steps)}")
    candidate_ids = program.get("candidate_ids")
    if isinstance(candidate_ids, list):
        summary_parts.append(f"candidates={len(candidate_ids)}")
    plan = program.get("plan") or program.get("plan_summary") or program.get("strategy")
    if plan:
        plan_text = json.dumps(plan) if isinstance(plan, (dict, list)) else str(plan)
        plan_text = plan_text.replace("\n", " ").strip()
        if len(plan_text) > 120:
            plan_text = f"{plan_text[:120]}…"
        summary_parts.append(f"plan={plan_text}")
    if not summary_parts:
        summary_parts.append(f"keys={sorted(program.keys())}")
    return ", ".join(summary_parts)


def _final_answer_preview(final_answer: str | None, final: dict | None) -> str:
    answer = final_answer
    if answer is None and final:
        raw = final.get("answer")
        if raw is not None:
            answer = str(raw)
    if not answer:
        return ""
    answer = answer.replace("\n", " ").strip()
    if len(answer) > 300:
        return f"{answer[:300]}…"
    return answer


def _print_run_summary(result: dict) -> None:
    program_summary = _summarize_program(result.get("program") or {})
    final_preview = _final_answer_preview(result.get("final_answer"), result.get("final"))
    print("Run response summary:")
    print(f"  run_id: {result.get('run_id')}")
    print(f"  status: {result.get('status')}")
    print(f"  program/plan summary: {program_summary}")
    print(f"  glimpses count: {len(result.get('glimpses') or [])}")
    print(f"  subcalls count: {len(result.get('subcalls') or [])}")
    print(f"  final_answer preview: {final_preview}")


def _print_run_summary_from_result(result: RunResult) -> None:
    program_summary = _summarize_program(result.program)
    final_preview = _final_answer_preview(result.final_answer, result.final)
    print("Run response summary:")
    print(f"  run_id: {result.run_id}")
    print(f"  status: {result.status}")
    print(f"  program/plan summary: {program_summary}")
    print(f"  glimpses count: {len(result.glimpses)}")
    print(f"  subcalls count: {len(result.subcalls)}")
    print(f"  final_answer preview: {final_preview}")


def _print_rounds_for_run(run_id: str) -> None:
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("select meta from rlm_runs where id = :run_id"),
            {"run_id": run_id},
        ).mappings().first()
    if not row:
        print("Round metadata: not found")
        return
    meta = row.get("meta") or {}
    if not isinstance(meta, dict) or not meta:
        print("Round metadata: empty")
        return
    print("Round metadata summary:")
    for key in ("round1", "round2", "round3"):
        info = meta.get(key) or {}
        stage = info.get("stage") or "unknown"
        mode = info.get("mode")
        status = info.get("status")
        details = [f"stage={stage}"]
        if mode:
            details.append(f"mode={mode}")
        if status:
            details.append(f"status={status}")
        print(f"  {key}: {', '.join(details)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Demo RLM run flow")
    parser.add_argument("--project", default="demo-rlm", help="project name")
    parser.add_argument("--query", default="What is this session about?", help="query text")
    parser.add_argument(
        "--base-url",
        default=os.getenv("RLM_BASE_URL", "http://backend:8000"),
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
        resp = _call_run(args.base_url, session_id, args.query)
        _print_run_summary(resp)
        _print_rounds_for_run(resp.get("run_id"))
    except Exception as exc:  # noqa: BLE001 - demo script should surface error
        print(f"Failed to call run API at {args.base_url}: {exc}", file=sys.stderr)
        print(
            "Falling back to direct runner invocation. "
            "Ensure migrations are applied (alembic upgrade head), "
            "the backend is healthy (docker compose up -d backend), "
            "and RLM_BASE_URL/--base-url points to the running API.",
            file=sys.stderr,
        )
        try:
            direct_result = _direct_run(session_id, args.query)
            _print_run_summary_from_result(direct_result)
            _print_rounds_for_run(direct_result.run_id)
        except Exception as direct_exc:  # noqa: BLE001 - demo script should surface error
            print(f"Direct runner invocation failed: {direct_exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
