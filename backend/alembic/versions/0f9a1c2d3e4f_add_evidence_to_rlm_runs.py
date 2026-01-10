"""add evidence to rlm_runs

Revision ID: 0f9a1c2d3e4f
Revises: d5e8f1b2c3d4
Create Date: 2026-01-12 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0f9a1c2d3e4f"
down_revision: Union[str, None] = "d5e8f1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE rlm_runs
            ADD COLUMN IF NOT EXISTS evidence jsonb NOT NULL DEFAULT '[]'::jsonb;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE rlm_runs
            DROP COLUMN IF EXISTS evidence;
        """
    )
