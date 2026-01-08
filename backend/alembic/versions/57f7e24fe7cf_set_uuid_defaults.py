"""set uuid defaults

Revision ID: 57f7e24fe7cf
Revises: aad72ce7ce2e
Create Date: 2026-01-08
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "57f7e24fe7cf"
down_revision = "aad72ce7ce2e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute("ALTER TABLE projects ALTER COLUMN id SET DEFAULT gen_random_uuid();")
    op.execute("ALTER TABLE users ALTER COLUMN id SET DEFAULT gen_random_uuid();")
    op.execute("ALTER TABLE sessions ALTER COLUMN id SET DEFAULT gen_random_uuid();")


def downgrade() -> None:
    op.execute("ALTER TABLE sessions ALTER COLUMN id DROP DEFAULT;")
    op.execute("ALTER TABLE users ALTER COLUMN id DROP DEFAULT;")
    op.execute("ALTER TABLE projects ALTER COLUMN id DROP DEFAULT;")


