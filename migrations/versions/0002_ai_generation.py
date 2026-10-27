"""ai generation

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-26

Таблиці AI-генерації плану (contract.md §3.7): plan_generations, plan_generation_notices.

Використання ШІ: міграцію складено за допомогою Claude за моделями src/db/models/ai.py у стилі 0001.
Перевірка: upgrade/downgrade, `alembic check`, pytest.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plan_generations",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(always=False), nullable=False
        ),
        sa.Column("student_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("academic_year", sa.SmallInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "succeeded",
                "failed",
                name="generation_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("plan_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), nullable=False),
        sa.Column("prompt_sha256", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempts BETWEEN 0 AND 3", name=op.f("ck_plan_generations_attempts_range")),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["individual_plans.id"],
            name=op.f("fk_plan_generations_plan_id_individual_plans"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["users.id"], name=op.f("fk_plan_generations_student_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_generations")),
    )
    op.create_index(
        "ix_plan_generations_student_created", "plan_generations", ["student_id", "created_at"], unique=False
    )
    op.create_index(
        "uq_plan_generations_active_student",
        "plan_generations",
        ["student_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "plan_generation_notices",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(always=False), nullable=False
        ),
        sa.Column("generation_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("course_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_plan_generation_notices_course_id_courses"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["generation_id"],
            ["plan_generations.id"],
            name=op.f("fk_plan_generation_notices_generation_id_plan_generations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_generation_notices")),
    )
    op.create_index(
        op.f("ix_plan_generation_notices_generation_id"),
        "plan_generation_notices",
        ["generation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_plan_generation_notices_generation_id"), table_name="plan_generation_notices")
    op.drop_table("plan_generation_notices")
    op.drop_index(
        "uq_plan_generations_active_student",
        table_name="plan_generations",
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )
    op.drop_index("ix_plan_generations_student_created", table_name="plan_generations")
    op.drop_table("plan_generations")
