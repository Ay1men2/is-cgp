from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.rlm.domain.models import Candidate, CandidateIndex


class ArtifactRepo:
    """
    访问 artifacts 表的轻量 SQL 仓库。
    """

    def __init__(self, engine: Engine):
        self.engine = engine

    def get_content(self, artifact_id: str) -> dict[str, Any]:
        sql = text(
            """
            SELECT
                id::text AS artifact_id,
                content,
                content_hash,
                metadata
            FROM artifacts
            WHERE id = :artifact_id
            LIMIT 1
            """
        )
        with self.engine.connect() as conn:
            row = conn.execute(sql, {"artifact_id": artifact_id}).mappings().first()
            if not row:
                raise ValueError(f"artifact_id not found: {artifact_id}")
            return {
                "artifact_id": row["artifact_id"],
                "content": row["content"],
                "content_hash": row["content_hash"],
                "metadata": row.get("metadata") or {},
            }


@dataclass(frozen=True)
class RetrievalOptions:
    include_global: bool = True
    top_k: int = 20
    preview_chars: int = 240
    allowed_types: list[str] = field(default_factory=list)


class RlmRepoSQL:
    """
    只做“集中 SQL”，不引入 ORM，不做额外 DB helper。
    Engine/Connection 由上游 deps.py 提供。
    """

    def __init__(self, engine: Engine):
        self.engine = engine

    # --- helpers ---
    def _get_project_id_by_session(self, session_id: str) -> str:
        """
        返回 session 对应的 project_id（text）。
        注意：不要写 :session_id::uuid 这种形式，会在 SQLAlchemy text() 里炸。
        """
        sql = text(
            """
            SELECT project_id::text AS project_id
            FROM sessions
            WHERE id = :session_id
            LIMIT 1
            """
        )
        with self.engine.connect() as conn:
            row = conn.execute(sql, {"session_id": session_id}).mappings().first()
            if not row:
                raise ValueError(f"session_id not found: {session_id}")
            return row["project_id"]

    # --- artifacts retrieval ---
    def list_candidates(
        self,
        session_id: str,
        query: str,
        tokens: list[str],
        opt: RetrievalOptions,
    ) -> CandidateIndex:
        project_id = self._get_project_id_by_session(session_id)

        # scope 条件（session/project/global）
        scopes: list[str] = ["session", "project"]
        if opt.include_global:
            scopes.append("global")

        # 关键点：
        # 1) 不要用 :session_id::uuid / :project_id::uuid
        # 2) tokens 不强贴 ::text[]，直接 unnest(:tokens)，让驱动适配 array
        # 3) session scope 需要 session_id 约束；project/global 不需要
        sql = text(
            """
            SELECT
                id::text AS artifact_id,
                scope,
                type,
                title,
                content_hash,
                pinned,
                weight,
                source,
                token_estimate,
                content_hash,
                left(content, :preview_chars) AS content_preview,

                (
                    SELECT count(*)
                    FROM unnest(:tokens) AS t
                    WHERE content ILIKE ('%' || t || '%')
                ) AS hit_count

            FROM artifacts
            WHERE status = 'active'
              AND project_id = :project_id
              AND scope = ANY(:scopes)
              AND (:allowed_types IS NULL OR type = ANY(:allowed_types))
              AND (
                    (scope = 'session' AND session_id = :session_id)
                 OR (scope <> 'session')
              )
            ORDER BY pinned DESC, weight DESC, hit_count DESC, created_at DESC
            LIMIT :top_k
            """
        )

        with self.engine.connect() as conn:
            allowed_types = opt.allowed_types or None
            rows = conn.execute(
                sql,
                {
                    "project_id": project_id,
                    "session_id": session_id,
                    "scopes": scopes,
                    "allowed_types": allowed_types,
                    "tokens": tokens,
                    "top_k": opt.top_k,
                    "preview_chars": opt.preview_chars,
                },
            ).mappings().all()

        candidates: list[Candidate] = []
        for r in rows:
            hit_count = float(r.get("hit_count") or 0.0)
            weight = float(r.get("weight") or 1.0)
            pinned = bool(r.get("pinned"))

            base_score = weight + (0.2 * hit_count) + (5.0 if pinned else 0.0)

            candidates.append(
                Candidate(
                    artifact_id=r["artifact_id"],
                    scope=r["scope"],
                    type=r["type"],
                    title=r.get("title"),
                    content_hash=r["content_hash"],
                    pinned=pinned,
                    weight=weight,
                    source=r.get("source") or "manual",
                    content_preview=r.get("content_preview") or "",
                    content_hash=r.get("content_hash"),
                    token_estimate=r.get("token_estimate"),
                    base_score=base_score,
                    score_breakdown={
                        "weight": weight,
                        "hit_count": hit_count,
                        "pinned_bonus": 5.0 if pinned else 0.0,
                    },
                )
            )

        return CandidateIndex(
            session_id=session_id,
            project_id=project_id,
            query=query,
            candidates=candidates,
        )

    # --- rlm_runs write (minimal) ---
    def insert_run(
        self,
        session_id: str,
        query: str,
        options: dict | None = None,
        candidate_index: dict | None = None,
    ) -> str:
        """
        写入一条 rlm_runs 记录（v0：只落 options + candidate_index）
        这里的 jsonb cast 不会触发你遇到的 :param::type 问题，因为我们是对 SQL literal cast：
        :options::jsonb OK（注意：这是在 VALUES 里，属于 SQL 表达式；不是 WHERE 里 :id::uuid 那种）
        """
        options = options or {}
        candidate_index = candidate_index or {}
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    INSERT INTO rlm_runs (session_id, query, options, candidate_index, status)
                    VALUES (:session_id, :query, :options::jsonb, :candidate_index::jsonb, 'ok')
                    RETURNING id::text AS id
                    """
                ),
                {
                    "session_id": session_id,
                    "query": query,
                    "options": json.dumps(options),
                    "candidate_index": json.dumps(candidate_index),
                },
            ).mappings().one()
            return row["id"]

    def append_round(
        self,
        run_id: str,
        round_payload: list[dict] | dict,
        llm_raw_append: list[dict] | dict | None = None,
        errors_append: list[dict] | dict | None = None,
    ) -> None:
        if isinstance(round_payload, dict):
            round_payload = [round_payload]
        if isinstance(llm_raw_append, dict):
            llm_raw_append = [llm_raw_append]
        if isinstance(errors_append, dict):
            errors_append = [errors_append]

        llm_raw_append = llm_raw_append or []
        errors_append = errors_append or []

        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE rlm_runs
                    SET
                        rounds = COALESCE(rounds, '[]'::jsonb) || :round_payload::jsonb,
                        llm_raw = COALESCE(llm_raw, '[]'::jsonb) || :llm_raw_append::jsonb,
                        errors = COALESCE(errors, '[]'::jsonb) || :errors_append::jsonb
                    WHERE id = :run_id
                    """
                ),
                {
                    "run_id": run_id,
                    "round_payload": json.dumps(round_payload),
                    "llm_raw_append": json.dumps(llm_raw_append),
                    "errors_append": json.dumps(errors_append),
                },
            )

    def update_run(self, run_id: str, patch_jsonb: dict[str, Any]) -> None:
        if not patch_jsonb:
            return

        events_payload = self._normalize_list_payload(patch_jsonb.get("events"))
        update_clauses: list[str] = []
        params: dict[str, Any] = {"run_id": run_id}

        if "program" in patch_jsonb:
            update_clauses.append("program = :program::jsonb")
            params["program"] = json.dumps(patch_jsonb.get("program") or [])
        if "program_meta" in patch_jsonb:
            update_clauses.append("program_meta = :program_meta::jsonb")
            params["program_meta"] = json.dumps(patch_jsonb.get("program_meta") or {})
        if "events" in patch_jsonb:
            update_clauses.append("events = COALESCE(events, '[]'::jsonb) || :events::jsonb")
            params["events"] = json.dumps(events_payload)
        if "glimpses" in patch_jsonb:
            update_clauses.append("glimpses = COALESCE(glimpses, '[]'::jsonb) || :glimpses::jsonb")
            params["glimpses"] = json.dumps(self._normalize_list_payload(patch_jsonb.get("glimpses")))
        if "subcalls" in patch_jsonb:
            update_clauses.append("subcalls = COALESCE(subcalls, '[]'::jsonb) || :subcalls::jsonb")
            params["subcalls"] = json.dumps(self._normalize_list_payload(patch_jsonb.get("subcalls")))
        if "final_answer" in patch_jsonb:
            update_clauses.append("final_answer = :final_answer")
            params["final_answer"] = patch_jsonb.get("final_answer")
        if "citations" in patch_jsonb:
            update_clauses.append("citations = COALESCE(citations, '[]'::jsonb) || :citations::jsonb")
            params["citations"] = json.dumps(self._normalize_list_payload(patch_jsonb.get("citations")))
        if "options" in patch_jsonb:
            update_clauses.append("options = :options::jsonb")
            params["options"] = json.dumps(patch_jsonb.get("options") or {})
        if "candidate_index" in patch_jsonb:
            update_clauses.append("candidate_index = :candidate_index::jsonb")
            params["candidate_index"] = json.dumps(patch_jsonb.get("candidate_index") or {})
        if "errors" in patch_jsonb:
            update_clauses.append("errors = COALESCE(errors, '[]'::jsonb) || :errors::jsonb")
            params["errors"] = json.dumps(self._normalize_list_payload(patch_jsonb.get("errors")))
        if "status" in patch_jsonb:
            update_clauses.append("status = :status")
            params["status"] = patch_jsonb.get("status")

        if not update_clauses:
            return

        with self.engine.begin() as conn:
            if events_payload:
                conn.execute(
                    text(
                        """
                        INSERT INTO rlm_run_events (run_id, event)
                        VALUES (:run_id, :event::jsonb)
                        """
                    ),
                    [
                        {"run_id": run_id, "event": json.dumps(event)}
                        for event in events_payload
                    ],
                )
            conn.execute(
                text(
                    f"""
                    UPDATE rlm_runs
                    SET {", ".join(update_clauses)}
                    WHERE id = :run_id
                    """
                ),
                params,
            )

    def finish_run(
        self,
        run_id: str,
        assembled_context: dict,
        rendered_prompt: str | None,
        status: str,
        errors: list[dict] | dict | None = None,
    ) -> None:
        if isinstance(errors, dict):
            errors = [errors]
        errors = errors or []

        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE rlm_runs
                    SET
                        assembled_context = :assembled_context::jsonb,
                        rendered_prompt = :rendered_prompt,
                        status = :status,
                        errors = :errors::jsonb
                    WHERE id = :run_id
                    """
                ),
                {
                    "run_id": run_id,
                    "assembled_context": json.dumps(assembled_context),
                    "rendered_prompt": rendered_prompt,
                    "status": status,
                    "errors": json.dumps(errors),
                },
            )

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
        final: dict,
        final_answer: str | None,
        citations: list[Any],
        status: str,
        errors: list[dict] | dict | None = None,
    ) -> None:
        if isinstance(errors, dict):
            errors = [errors]
        errors = errors or []

        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE rlm_runs
                    SET
                        program = :program::jsonb,
                        meta = :meta::jsonb,
                        events = :events::jsonb,
                        glimpses = :glimpses::jsonb,
                        glimpses_meta = :glimpses_meta::jsonb,
                        subcalls = :subcalls::jsonb,
                        final = :final::jsonb,
                        final_answer = :final_answer,
                        citations = :citations::jsonb,
                        status = :status,
                        errors = :errors::jsonb
                    WHERE id = :run_id
                    """
                ),
                {
                    "run_id": run_id,
                    "program": json.dumps(program),
                    "meta": json.dumps(meta),
                    "events": json.dumps(events),
                    "glimpses": json.dumps(glimpses),
                    "glimpses_meta": json.dumps(glimpses_meta),
                    "subcalls": json.dumps(subcalls),
                    "final": json.dumps(final),
                    "final_answer": final_answer,
                    "citations": json.dumps(citations),
                    "status": status,
                    "errors": json.dumps(errors),
                },
            )
    @staticmethod
    def _normalize_list_payload(payload: Any) -> list[Any]:
        if payload is None:
            return []
        if isinstance(payload, list):
            return payload
        return [payload]
