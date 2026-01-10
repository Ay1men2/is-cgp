"""merge heads

Revision ID: 18b70efebe11
Revises: 0f9a1c2d3e4f, 9a4c7d1b2f01, 9c1b2f3a4d5e
Create Date: 2026-01-10 20:28:47.199746

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '18b70efebe11'
down_revision: Union[str, None] = ('0f9a1c2d3e4f', '9a4c7d1b2f01', '9c1b2f3a4d5e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
