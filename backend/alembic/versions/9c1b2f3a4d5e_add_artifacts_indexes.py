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
    op.create_index(
        'idx_artifacts_project_scope_status_pinned',
        'artifacts',
        ['project_id', 'scope', 'status', 'pinned'],
    )
    op.create_index(
        'idx_artifacts_session_scope_status_pinned',
        'artifacts',
        ['session_id', 'scope', 'status', 'pinned'],
    )



def downgrade() -> None:
    op.drop_index('idx_artifacts_session_scope_status_pinned', table_name='artifacts')
    op.drop_index('idx_artifacts_project_scope_status_pinned', table_name='artifacts')
