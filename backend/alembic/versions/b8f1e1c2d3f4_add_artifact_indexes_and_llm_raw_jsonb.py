"""add artifact indexes and llm_raw jsonb

Revision ID: b8f1e1c2d3f4
Revises: 374c3ab5b478
Create Date: 2026-01-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b8f1e1c2d3f4"
down_revision: Union[str, None] = "374c3ab5b478"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_artifacts_project_scope_status_pinned
            ON artifacts (project_id, scope, status, pinned);

        CREATE INDEX IF NOT EXISTS idx_artifacts_session_scope_status_pinned
            ON artifacts (session_id, scope, status, pinned);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_artifacts_active_unique_content
            ON artifacts (
                project_id,
                scope,
                type,
                COALESCE(session_id, '00000000-0000-0000-0000-000000000000'::uuid),
                content_hash
            )
            WHERE status = 'active';

        CREATE INDEX IF NOT EXISTS idx_artifacts_metadata_gin
            ON artifacts USING GIN (metadata);
        """
    )

    op.execute(
        """
        ALTER TABLE rlm_runs
            ALTER COLUMN llm_raw DROP DEFAULT,
            ALTER COLUMN llm_raw TYPE jsonb
                USING (
                    CASE
                        WHEN llm_raw IS NULL OR llm_raw = '' THEN '[]'::jsonb
                        ELSE jsonb_build_array(jsonb_build_object('raw', llm_raw))
                    END
                ),
            ALTER COLUMN llm_raw SET DEFAULT '[]'::jsonb,
            ALTER COLUMN llm_raw SET NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE rlm_runs
            ALTER COLUMN llm_raw DROP DEFAULT,
            ALTER COLUMN llm_raw TYPE text
                USING (
                    CASE
                        WHEN llm_raw IS NULL THEN ''
                        WHEN jsonb_typeof(llm_raw) = 'array' AND jsonb_array_length(llm_raw) > 0
                            THEN COALESCE(llm_raw->0->>'raw', '')
                        ELSE ''
                    END
                ),
            ALTER COLUMN llm_raw SET DEFAULT '',
            ALTER COLUMN llm_raw SET NOT NULL;
        """
    )

    op.execute(
        """
        DROP INDEX IF EXISTS idx_artifacts_metadata_gin;
        DROP INDEX IF EXISTS idx_artifacts_active_unique_content;
        DROP INDEX IF EXISTS idx_artifacts_session_scope_status_pinned;
        DROP INDEX IF EXISTS idx_artifacts_project_scope_status_pinned;
        """
    )
