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
        # 2) array 参数显式 cast 为 text[]，避免 Postgres unnest/ANY 识别为 unknown
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
                left(content, :preview_chars) AS content_preview,

                (
                    SELECT count(*)
                    FROM unnest(CAST(:tokens AS text[])) AS t(token)
                    WHERE content ILIKE ('%' || token || '%')
                ) AS hit_count

            FROM artifacts
            WHERE status = 'active'
              AND project_id = :project_id
              AND scope = ANY(CAST(:scopes AS text[]))
              AND (CAST(:allowed_types AS text[]) IS NULL
                   OR type = ANY(CAST(:allowed_types AS text[])))
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

    def _fetch_artifact_row(self, artifact_id: str) -> dict[str, Any] | None:
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
            return None
        return {
            "artifact_id": row["artifact_id"],
            "content": row["content"],
            "content_hash": row["content_hash"],
            "metadata": row.get("metadata") or {},
        }

    def get_artifact_text(self, artifact_id: str) -> str | None:
        """
        返回 artifacts.content 全文；未找到返回 None。
        """
        row = self._fetch_artifact_row(artifact_id)
        if not row:
            return None
        content = row.get("content")
        if not isinstance(content, str) or not content:
            return None
        return content

    def get_artifact_metadata(self, artifact_id: str) -> dict[str, Any]:
        """
        返回 artifacts metadata 与 content_hash（未找到返回空 dict）。
        """
        row = self._fetch_artifact_row(artifact_id)
        if not row:
            return {}
        return {
            "artifact_id": row.get("artifact_id"),
            "content_hash": row.get("content_hash"),
            "metadata": row.get("metadata") or {},
        }

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
        这里使用 CAST(:param AS jsonb) 避免 SQLAlchemy text() 的 :param::type 解析问题。
        """
        options = options or {}
        candidate_index = candidate_index or {}
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    INSERT INTO rlm_runs (session_id, query, options, candidate_index, status)
                    VALUES (:session_id, :query, CAST(:options AS jsonb), CAST(:candidate_index AS jsonb), 'ok')
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
                        rounds = COALESCE(rounds, '[]'::jsonb) || CAST(:round_payload AS jsonb),
                        llm_raw = COALESCE(llm_raw, '[]'::jsonb) || CAST(:llm_raw_append AS jsonb),
                        errors = COALESCE(errors, '[]'::jsonb) || CAST(:errors_append AS jsonb)
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
            update_clauses.append("program = CAST(:program AS jsonb)")
            params["program"] = json.dumps(patch_jsonb.get("program") or [])
        if "program_meta" in patch_jsonb:
            update_clauses.append("program_meta = CAST(:program_meta AS jsonb)")
            params["program_meta"] = json.dumps(patch_jsonb.get("program_meta") or {})
        if "events" in patch_jsonb:
            update_clauses.append(
                "events = COALESCE(events, '[]'::jsonb) || CAST(:events AS jsonb)"
            )
            params["events"] = json.dumps(events_payload)
        if "glimpses" in patch_jsonb:
            update_clauses.append(
                "glimpses = COALESCE(glimpses, '[]'::jsonb) || CAST(:glimpses AS jsonb)"
            )
            params["glimpses"] = json.dumps(self._normalize_list_payload(patch_jsonb.get("glimpses")))
        if "subcalls" in patch_jsonb:
            update_clauses.append(
                "subcalls = COALESCE(subcalls, '[]'::jsonb) || CAST(:subcalls AS jsonb)"
            )
            params["subcalls"] = json.dumps(self._normalize_list_payload(patch_jsonb.get("subcalls")))
        if "evidence" in patch_jsonb:
            update_clauses.append(
                "evidence = COALESCE(evidence, '[]'::jsonb) || CAST(:evidence AS jsonb)"
            )
            params["evidence"] = json.dumps(self._normalize_list_payload(patch_jsonb.get("evidence")))
        if "final_answer" in patch_jsonb:
            update_clauses.append("final_answer = :final_answer")
            params["final_answer"] = patch_jsonb.get("final_answer")
        if "citations" in patch_jsonb:
            update_clauses.append(
                "citations = COALESCE(citations, '[]'::jsonb) || CAST(:citations AS jsonb)"
            )
            params["citations"] = json.dumps(self._normalize_list_payload(patch_jsonb.get("citations")))
        if "options" in patch_jsonb:
            update_clauses.append("options = CAST(:options AS jsonb)")
            params["options"] = json.dumps(patch_jsonb.get("options") or {})
        if "candidate_index" in patch_jsonb:
            update_clauses.append("candidate_index = CAST(:candidate_index AS jsonb)")
            params["candidate_index"] = json.dumps(patch_jsonb.get("candidate_index") or {})
        if "errors" in patch_jsonb:
            update_clauses.append(
                "errors = COALESCE(errors, '[]'::jsonb) || CAST(:errors AS jsonb)"
            )
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
                        VALUES (:run_id, CAST(:event AS jsonb))
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
                        assembled_context = CAST(:assembled_context AS jsonb),
                        rendered_prompt = :rendered_prompt,
                        status = :status,
                        errors = CAST(:errors AS jsonb)
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
        evidence: list[dict],
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
                        program = CAST(:program AS jsonb),
                        meta = CAST(:meta AS jsonb),
                        events = CAST(:events AS jsonb),
                        glimpses = CAST(:glimpses AS jsonb),
                        glimpses_meta = CAST(:glimpses_meta AS jsonb),
                        subcalls = CAST(:subcalls AS jsonb),
                        evidence = CAST(:evidence AS jsonb),
                        final = CAST(:final AS jsonb),
                        final_answer = :final_answer,
                        citations = CAST(:citations AS jsonb),
                        status = :status,
                        errors = CAST(:errors AS jsonb)
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
                    "evidence": json.dumps(evidence),
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
