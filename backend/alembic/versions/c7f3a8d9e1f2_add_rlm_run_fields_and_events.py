"""add rlm run fields and events table

Revision ID: c7f3a8d9e1f2
Revises: b8f1e1c2d3f4
Create Date: 2026-01-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c7f3a8d9e1f2"
down_revision: Union[str, None] = "b8f1e1c2d3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE rlm_runs
            ADD COLUMN IF NOT EXISTS program jsonb NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS program_meta jsonb NOT NULL DEFAULT '{}'::jsonb,
            ADD COLUMN IF NOT EXISTS events jsonb NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS subcalls jsonb NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS final_answer text NULL,
            ADD COLUMN IF NOT EXISTS citations jsonb NOT NULL DEFAULT '[]'::jsonb;

        UPDATE rlm_runs
        SET glimpses = '[]'::jsonb
        WHERE glimpses IS NULL;

        ALTER TABLE rlm_runs
            ALTER COLUMN glimpses SET DEFAULT '[]'::jsonb,
            ALTER COLUMN glimpses SET NOT NULL;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rlm_run_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id uuid NOT NULL REFERENCES rlm_runs(id) ON DELETE CASCADE,
            event jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS idx_rlm_run_events_run_created
            ON rlm_run_events (run_id, created_at DESC);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS rlm_run_events;

        ALTER TABLE rlm_runs
            DROP COLUMN IF EXISTS program,
            DROP COLUMN IF EXISTS program_meta,
            DROP COLUMN IF EXISTS events,
            DROP COLUMN IF EXISTS subcalls,
            DROP COLUMN IF EXISTS final_answer,
            DROP COLUMN IF EXISTS citations;

        ALTER TABLE rlm_runs
            ALTER COLUMN glimpses DROP NOT NULL,
            ALTER COLUMN glimpses DROP DEFAULT;
        """
    )
