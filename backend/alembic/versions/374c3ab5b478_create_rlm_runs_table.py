"""create rlm_runs table

Revision ID: 374c3ab5b478
Revises: f4cd1b4b247d
Create Date: 2026-01-09 23:13:40.484181

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '374c3ab5b478'
down_revision: Union[str, None] = 'f4cd1b4b247d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("""
    CREATE EXTENSION IF NOT EXISTS pgcrypto;

    CREATE TABLE IF NOT EXISTS rlm_runs (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

        session_id uuid NOT NULL,
        query text NOT NULL,

        options jsonb NOT NULL DEFAULT '{}'::jsonb,
        candidate_index jsonb NOT NULL DEFAULT '[]'::jsonb,
        rounds jsonb NOT NULL DEFAULT '[]'::jsonb,
        glimpses jsonb NULL,

        assembled_context jsonb NOT NULL DEFAULT '{}'::jsonb,
        rendered_prompt text NULL,

        llm_raw text NOT NULL DEFAULT '',

        status text NOT NULL DEFAULT 'ok',      -- ok|degraded|error
        errors jsonb NOT NULL DEFAULT '[]'::jsonb,

        created_at timestamptz NOT NULL DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS idx_rlm_runs_session_created
        ON rlm_runs (session_id, created_at DESC);

    CREATE INDEX IF NOT EXISTS idx_rlm_runs_status
        ON rlm_runs (status);

    CREATE INDEX IF NOT EXISTS idx_rlm_runs_created_at
        ON rlm_runs (created_at DESC);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS rlm_runs;")

