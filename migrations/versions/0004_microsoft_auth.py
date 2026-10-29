import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM refresh_tokens")
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "google_sub", new_column_name="ms_oid", existing_type=sa.String(255), existing_nullable=False
        )
        batch_op.add_column(sa.Column("ms_tid", sa.String(36), nullable=True))
        batch_op.drop_constraint(batch_op.f("uq_users_google_sub"), type_="unique")
        batch_op.create_unique_constraint(batch_op.f("uq_users_ms_oid"), ["ms_oid"])

    with op.batch_alter_table("refresh_tokens") as batch_op:
        batch_op.add_column(sa.Column("family_id", sa.String(32), nullable=False))
        batch_op.create_index("ix_refresh_tokens_family_id", ["family_id"])


def downgrade() -> None:
    op.execute("DELETE FROM refresh_tokens")
    with op.batch_alter_table("refresh_tokens") as batch_op:
        batch_op.drop_index("ix_refresh_tokens_family_id")
        batch_op.drop_column("family_id")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint(batch_op.f("uq_users_ms_oid"), type_="unique")
        batch_op.create_unique_constraint(batch_op.f("uq_users_google_sub"), ["ms_oid"])
        batch_op.drop_column("ms_tid")
        batch_op.alter_column(
            "ms_oid", new_column_name="google_sub", existing_type=sa.String(255), existing_nullable=False
        )
