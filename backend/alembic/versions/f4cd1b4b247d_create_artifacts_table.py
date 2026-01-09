"""create artifacts table

Revision ID: f4cd1b4b247d
Revises: 346ccb62d31e
Create Date: 2026-01-09 23:13:40.211606

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4cd1b4b247d'
down_revision: Union[str, None] = '346ccb62d31e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("""
    CREATE EXTENSION IF NOT EXISTS pgcrypto;

    CREATE TABLE IF NOT EXISTS artifacts (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

        project_id uuid NOT NULL,
        session_id uuid NULL,

        scope text NOT NULL,     -- global|project|session
        type text NOT NULL,      -- doc|code|note|cache

        title text NULL,
        content text NOT NULL,

        content_hash text NOT NULL,
        token_estimate integer NULL,

        metadata jsonb NOT NULL DEFAULT '{}'::jsonb,

        weight real NOT NULL DEFAULT 1.0,
        pinned boolean NOT NULL DEFAULT false,

        source text NOT NULL DEFAULT 'manual',   -- manual|import|system|llm_suggestion|cache
        status text NOT NULL DEFAULT 'active',   -- active|archived|deleted

        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS idx_artifacts_project_scope_status
        ON artifacts (project_id, scope, status);

    CREATE INDEX IF NOT EXISTS idx_artifacts_session_scope_status
        ON artifacts (session_id, scope, status);

    CREATE INDEX IF NOT EXISTS idx_artifacts_pinned
        ON artifacts (pinned);

    CREATE INDEX IF NOT EXISTS idx_artifacts_content_hash
        ON artifacts (content_hash);

    CREATE INDEX IF NOT EXISTS idx_artifacts_source
        ON artifacts (source);

    CREATE INDEX IF NOT EXISTS idx_artifacts_created_at
        ON artifacts (created_at DESC);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS artifacts;")


