"""Persist per-semester SAZ weekly hours without inventing legacy values.

Використання ШІ: Codex додав міграцію #291; перевірка: upgrade/downgrade, pytest.
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("courses", sa.Column("semesters", sa.JSON(), nullable=False, server_default="[]"))


def downgrade():
    op.drop_column("courses", "semesters")
