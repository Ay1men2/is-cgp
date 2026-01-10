from __future__ import annotations

import json
from dataclasses import dataclass, field

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
        tokens: list[str],
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
              AND type = ANY(:types)
              AND scope = ANY(:scopes)
              AND (:types IS NULL OR type = ANY(:types))
              AND (
                    (scope = 'session' AND session_id = :session_id)
                 OR (scope <> 'session')
              )
            ORDER BY pinned DESC, weight DESC, hit_count DESC, created_at DESC
            LIMIT :top_k
            """
        )

        with self.engine.connect() as conn:
            rows = conn.execute(
                sql,
                {
                    "project_id": project_id,
                    "session_id": session_id,
                    "scopes": scopes,
                    "types": opt.allowed_types,
                    "tokens": tokens,
                    "top_k": opt.top_k,
                    "preview_chars": opt.preview_chars,
                    "types": opt.types,
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
