"""add glimpses_meta to rlm_runs

Revision ID: d5e8f1b2c3d4
Revises: c7f3a8d9e1f2
Create Date: 2026-01-13 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d5e8f1b2c3d4"
down_revision: Union[str, None] = "c7f3a8d9e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE rlm_runs
            ADD COLUMN IF NOT EXISTS glimpses_meta jsonb NOT NULL DEFAULT '[]'::jsonb;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE rlm_runs
            DROP COLUMN IF EXISTS glimpses_meta;
        """
    )
