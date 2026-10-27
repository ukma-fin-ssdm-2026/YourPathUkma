"""certificate programs

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

import src.db.base

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_ID = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "certificate_programs",
        sa.Column("id", _ID, sa.Identity(always=False), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("direction_ids", sa.ARRAY(sa.Integer()).with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column("hidden", sa.Boolean(), nullable=False),
        sa.Column(
            "availability",
            sa.Enum(
                "AVAILABLE",
                "UNAVAILABLE",
                name="certificate_availability",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("created_at", src.db.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column("updated_at", src.db.base.UTCDateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_certificate_programs")),
    )

    op.create_table(
        "certificate_program_courses",
        sa.Column("id", _ID, sa.Identity(always=False), nullable=False),
        sa.Column("program_id", _ID, nullable=False),
        sa.Column("course_id", _ID, nullable=True),
        sa.Column("raw_title", sa.String(length=300), nullable=False),
        sa.ForeignKeyConstraint(
            ["program_id"],
            ["certificate_programs.id"],
            name=op.f("fk_certificate_program_courses_program_id_certificate_programs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_certificate_program_courses_course_id_courses"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_certificate_program_courses")),
    )
    op.create_index("ix_certificate_program_courses_course_id", "certificate_program_courses", ["course_id"])
    op.create_index("ix_certificate_program_courses_program_id", "certificate_program_courses", ["program_id"])


def downgrade() -> None:
    op.drop_index("ix_certificate_program_courses_program_id", table_name="certificate_program_courses")
    op.drop_index("ix_certificate_program_courses_course_id", table_name="certificate_program_courses")
    op.drop_table("certificate_program_courses")
    op.drop_table("certificate_programs")
