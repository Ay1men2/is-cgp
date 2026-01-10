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
    # Deprecated: consolidated into c7f3a8d9e1f2_add_rlm_run_fields_and_events.py.
    # Keep as no-op to avoid overlapping column adds when branches are merged.
    pass


def downgrade() -> None:
    # See upgrade() note - no-op.
    pass
