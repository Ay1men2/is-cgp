"""merge migration heads

Revision ID: 346ccb62d31e
Revises: 57f7e24fe7cf, 7b6fd2016e11
Create Date: 2026-01-09 22:57:44.816079

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '346ccb62d31e'
down_revision: Union[str, None] = ('57f7e24fe7cf', '7b6fd2016e11')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
