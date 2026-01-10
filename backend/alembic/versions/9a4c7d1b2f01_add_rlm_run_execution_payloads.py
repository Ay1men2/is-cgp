"""add rlm run execution payloads

Revision ID: 9a4c7d1b2f01
Revises: b8f1e1c2d3f4
Create Date: 2026-01-11 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9a4c7d1b2f01"
down_revision: Union[str, None] = "b8f1e1c2d3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE rlm_runs
            ADD COLUMN IF NOT EXISTS program jsonb NOT NULL DEFAULT '{}'::jsonb,
            ADD COLUMN IF NOT EXISTS meta jsonb NOT NULL DEFAULT '{}'::jsonb,
            ADD COLUMN IF NOT EXISTS events jsonb NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS subcalls jsonb NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS final jsonb NOT NULL DEFAULT '{}'::jsonb;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE rlm_runs
            DROP COLUMN IF EXISTS final,
            DROP COLUMN IF EXISTS subcalls,
            DROP COLUMN IF EXISTS events,
            DROP COLUMN IF EXISTS meta,
            DROP COLUMN IF EXISTS program;
        """
    )
