"""add plan_alternatives table (FR-009)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-09

Використання ШІ: файл створено за допомогою Antigravity (Claude Sonnet 4.6, Google DeepMind).
Перевірено: alembic check, alembic upgrade head на тестовій БД.
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("plan_items") as batch_op:
        batch_op.add_column(sa.Column("ai_explanation", sa.Text(), nullable=True))

    op.create_table(
        "plan_alternatives",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(always=False), nullable=False
        ),
        sa.Column("plan_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("plan_item_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("course_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column(
            "trimester",
            sa.Enum(
                "autumn", "spring", "summer", name="trimester", native_enum=False, create_constraint=True, length=32
            ),
            nullable=False,
        ),
        sa.Column("explanation", sa.Text(), nullable=False, server_default=""),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint("rank BETWEEN 1 AND 3", name="rank_range"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plan_id"], ["individual_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_item_id"], ["plan_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plan_alternatives_plan_id", "plan_alternatives", ["plan_id"])
    op.create_index("ix_plan_alternatives_plan_item_id", "plan_alternatives", ["plan_item_id"])
    op.create_index("ix_plan_alternatives_course_id", "plan_alternatives", ["course_id"])


def downgrade() -> None:
    op.drop_index("ix_plan_alternatives_course_id", table_name="plan_alternatives")
    op.drop_index("ix_plan_alternatives_plan_item_id", table_name="plan_alternatives")
    op.drop_index("ix_plan_alternatives_plan_id", table_name="plan_alternatives")
    op.drop_table("plan_alternatives")

    with op.batch_alter_table("plan_items") as batch_op:
        batch_op.drop_column("ai_explanation")
