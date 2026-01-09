from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.rlm.domain.models import Candidate, CandidateIndex


@dataclass(frozen=True)
class RetrievalOptions:
    include_global: bool = True
    top_k: int = 20
    preview_chars: int = 240


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
            WHERE id = session_id
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
        opt: RetrievalOptions,
    ) -> CandidateIndex:
        project_id = self._get_project_id_by_session(session_id)

        # scope 条件（session/project/global）
        scopes: list[str] = ["session", "project"]
        if opt.include_global:
            scopes.append("global")

        # v0 最轻量 token：按空格切；最多 8 个，防止 OR/unnest 爆炸
        tokens = [t for t in query.replace("\n", " ").split(" ") if t.strip()]
        tokens = tokens[:8]
        if not tokens:
            tokens = [query]

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
                pinned,
                weight,
                source,
                token_estimate,
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
                    pinned=pinned,
                    weight=weight,
                    source=r.get("source") or "manual",
                    content_preview=r.get("content_preview") or "",
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
    def insert_run(self, session_id: str, query: str, options: dict, candidate_index: dict) -> str:
        """
        写入一条 rlm_runs 记录（v0：只落 options + candidate_index）
        这里的 jsonb cast 不会触发你遇到的 :param::type 问题，因为我们是对 SQL literal cast：
        :options::jsonb OK（注意：这是在 VALUES 里，属于 SQL 表达式；不是 WHERE 里 :id::uuid 那种）
        """
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

