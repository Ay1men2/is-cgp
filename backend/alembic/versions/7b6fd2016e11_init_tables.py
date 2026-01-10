"""init tables

Revision ID: 7b6fd2016e11
Revises: 
Create Date: 2026-01-06 10:41:54.083573

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b6fd2016e11'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Deprecated: core tables are created in aad72ce7ce2e_create_core_tables.py.
    # This migration remains as a no-op to avoid duplicate table creation
    # when the branch is merged via 346ccb62d31e.
    pass


def downgrade() -> None:
    # See upgrade() note - no-op.
    pass
