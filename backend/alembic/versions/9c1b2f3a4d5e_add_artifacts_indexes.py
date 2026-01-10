"""add artifacts indexes

Revision ID: 9c1b2f3a4d5e
Revises: f4cd1b4b247d
Create Date: 2026-01-10 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '9c1b2f3a4d5e'
down_revision: Union[str, None] = 'f4cd1b4b247d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Deprecated: indexes are created in b8f1e1c2d3f4_add_artifact_indexes_and_llm_raw_jsonb.py.
    # Keep as no-op to avoid duplicate index creation when branches are merged.
    pass



def downgrade() -> None:
    # See upgrade() note - no-op.
    pass
