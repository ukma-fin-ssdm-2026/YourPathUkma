"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-14

Початкова схема під MVP-кінцеві точки contract.md (✅ і 🟡). Таблиці етапу 2 (AI-генерація, альтернативи,
сертифікатні програми) додаватимуться окремими міграціями.

Використання ШІ: міграцію згенеровано `alembic revision --autogenerate` з моделей src/db/models, потім вручну
доопрацьовано за допомогою Claude (Claude Code): прибрано batch-режим, тип UTCDateTime замінено на DateTime,
додано тригер append-only для audit_log (PostgreSQL). Перевірка: upgrade/downgrade і `alembic check` на SQLite
і PostgreSQL, pytest.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "directions",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(always=False), nullable=False
        ),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("name_normalized", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_directions")),
        sa.UniqueConstraint("name_normalized", name=op.f("uq_directions_name_normalized")),
    )
    op.create_table(
        "instructors",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(always=False), nullable=False
        ),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("full_name_normalized", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_instructors")),
    )
    op.create_index(op.f("ix_instructors_full_name_normalized"), "instructors", ["full_name_normalized"], unique=False)

    op.create_table(
        "users",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(always=False), nullable=False
        ),
        sa.Column("google_sub", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column(
            "role",
            sa.Enum("student", "admin", name="user_role", native_enum=False, create_constraint=True, length=32),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("google_sub", name=op.f("uq_users_google_sub")),
    )
    op.create_table(
        "audit_log",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(always=False), nullable=False
        ),
        sa.Column("actor_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("object_type", sa.String(length=64), nullable=False),
        sa.Column("object_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column(
            "outcome",
            sa.Enum("allowed", "denied", name="audit_outcome", native_enum=False, create_constraint=True, length=32),
            nullable=False,
        ),
        sa.Column(
            "old_value", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True
        ),
        sa.Column(
            "new_value", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True
        ),
        sa.Column("ip", sa.String(length=45).with_variant(postgresql.INET(), "postgresql"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name=op.f("fk_audit_log_actor_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(op.f("ix_audit_log_actor_id"), "audit_log", ["actor_id"], unique=False)
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"], unique=False)
    op.create_index("ix_audit_log_object", "audit_log", ["object_type", "object_id"], unique=False)

    op.create_table(
        "deanery_plan_documents",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(always=False), nullable=False
        ),
        sa.Column("student_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("academic_year", sa.SmallInteger(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column(
            "mime_type",
            sa.Enum("pdf", "docx", name="document_mime_type", native_enum=False, create_constraint=True, length=32),
            nullable=False,
        ),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "parse_status",
            sa.Enum(
                "pending",
                "parsed",
                "failed",
                name="document_parse_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "size_bytes > 0 AND size_bytes <= 10485760", name=op.f("ck_deanery_plan_documents_size_bytes_range")
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["users.id"], name=op.f("fk_deanery_plan_documents_student_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deanery_plan_documents")),
    )
    op.create_table(
        "plan_preferences",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(always=False), nullable=False
        ),
        sa.Column("student_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("academic_year", sa.SmallInteger(), nullable=False),
        sa.Column("include_free_electives", sa.Boolean(), nullable=False),
        sa.Column("wants_certificate", sa.Boolean(), nullable=False),
        sa.Column("certificate_program_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["student_id"], ["users.id"], name=op.f("fk_plan_preferences_student_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_preferences")),
        sa.UniqueConstraint("student_id", "academic_year", name=op.f("uq_plan_preferences_student_id_academic_year")),
    )
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(always=False), nullable=False
        ),
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("token_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_refresh_tokens_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_sha256", name=op.f("uq_refresh_tokens_token_sha256")),
    )
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False)

    op.create_table(
        "student_profiles",
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("faculty", sa.String(length=100), nullable=False),
        sa.Column("specialty", sa.String(length=150), nullable=True),
        sa.Column("course_year", sa.SmallInteger(), nullable=True),
        sa.Column(
            "course_year_source",
            sa.Enum(
                "self_declared",
                "admin",
                "saz_sync",
                name="course_year_source",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column("saz_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("course_year BETWEEN 1 AND 4", name=op.f("ck_student_profiles_course_year_range")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_student_profiles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_student_profiles")),
    )
    op.create_table(
        "sync_jobs",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(always=False), nullable=False
        ),
        sa.Column(
            "source",
            sa.Enum(
                "saz_catalog",
                "faculty_certificates",
                name="sync_source",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "initiator",
            sa.Enum("admin", "scheduler", name="sync_initiator", native_enum=False, create_constraint=True, length=32),
            nullable=False,
        ),
        sa.Column("initiated_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "succeeded",
                "failed",
                name="sync_job_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("added_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_snapshot", sa.Text(), nullable=True),
        sa.Column("raw_snapshot_sha256", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["initiated_by"], ["users.id"], name=op.f("fk_sync_jobs_initiated_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_jobs")),
    )
    op.create_index("ix_sync_jobs_started_at", "sync_jobs", ["started_at"], unique=False)
    op.create_index(
        "uq_sync_jobs_active_source",
        "sync_jobs",
        ["source"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
        sqlite_where=sa.text("status IN ('queued', 'running')"),
    )

    op.create_table(
        "courses",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(always=False), nullable=False
        ),
        sa.Column("saz_code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("title_normalized", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("credits", sa.Numeric(precision=4, scale=1, asdecimal=False), nullable=False),
        sa.Column(
            "trimester",
            sa.Enum(
                "autumn", "spring", "summer", name="trimester", native_enum=False, create_constraint=True, length=32
            ),
            nullable=False,
        ),
        sa.Column("recommended_year", sa.SmallInteger(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("normative", "elective", name="course_kind", native_enum=False, create_constraint=True, length=32),
            nullable=False,
        ),
        sa.Column(
            "publication_status",
            sa.Enum(
                "published", "archived", name="publication_status", native_enum=False, create_constraint=True, length=32
            ),
            nullable=False,
        ),
        sa.Column("last_sync_job_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("credits > 0", name=op.f("ck_courses_credits_positive")),
        sa.CheckConstraint("recommended_year BETWEEN 1 AND 4", name=op.f("ck_courses_recommended_year_range")),
        sa.ForeignKeyConstraint(
            ["last_sync_job_id"],
            ["sync_jobs.id"],
            name=op.f("fk_courses_last_sync_job_id_sync_jobs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_courses")),
        sa.UniqueConstraint("saz_code", name=op.f("uq_courses_saz_code")),
    )
    op.create_index(op.f("ix_courses_title_normalized"), "courses", ["title_normalized"], unique=False)

    op.create_table(
        "individual_plans",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(always=False), nullable=False
        ),
        sa.Column("student_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("academic_year", sa.SmallInteger(), nullable=False),
        sa.Column("course_year", sa.SmallInteger(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "submitted",
                "awaiting_deanery",
                "approved",
                name="plan_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "origin",
            sa.Enum(
                "manual",
                "ai_generated",
                "saz_sync",
                name="plan_origin",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "load_autumn",
            sa.Enum("low", "medium", "high", name="load_autumn", native_enum=False, create_constraint=True, length=32),
            nullable=False,
        ),
        sa.Column(
            "load_spring",
            sa.Enum("low", "medium", "high", name="load_spring", native_enum=False, create_constraint=True, length=32),
            nullable=False,
        ),
        sa.Column(
            "load_summer",
            sa.Enum("low", "medium", "high", name="load_summer", native_enum=False, create_constraint=True, length=32),
            nullable=False,
        ),
        sa.Column("total_credits", sa.Numeric(precision=5, scale=1, asdecimal=False), nullable=False),
        sa.Column("preferences_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("deanery_document_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("course_year BETWEEN 2 AND 4", name=op.f("ck_individual_plans_course_year_range")),
        sa.CheckConstraint("total_credits >= 0", name=op.f("ck_individual_plans_total_credits_non_negative")),
        sa.ForeignKeyConstraint(
            ["deanery_document_id"],
            ["deanery_plan_documents.id"],
            name=op.f("fk_individual_plans_deanery_document_id_deanery_plan_documents"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["preferences_id"],
            ["plan_preferences.id"],
            name=op.f("fk_individual_plans_preferences_id_plan_preferences"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["users.id"], name=op.f("fk_individual_plans_student_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_individual_plans")),
    )
    op.create_index("ix_individual_plans_student_status", "individual_plans", ["student_id", "status"], unique=False)
    op.create_index(
        "ix_individual_plans_student_year", "individual_plans", ["student_id", "academic_year"], unique=False
    )

    op.create_table(
        "instructor_preferences",
        sa.Column("preferences_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("instructor_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "preferred",
                "unwanted",
                name="instructor_preference_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["instructor_id"],
            ["instructors.id"],
            name=op.f("fk_instructor_preferences_instructor_id_instructors"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["preferences_id"],
            ["plan_preferences.id"],
            name=op.f("fk_instructor_preferences_preferences_id_plan_preferences"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("preferences_id", "instructor_id", name=op.f("pk_instructor_preferences")),
    )
    op.create_index(
        op.f("ix_instructor_preferences_instructor_id"), "instructor_preferences", ["instructor_id"], unique=False
    )

    op.create_table(
        "preference_directions",
        sa.Column("preferences_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("direction_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.ForeignKeyConstraint(
            ["direction_id"],
            ["directions.id"],
            name=op.f("fk_preference_directions_direction_id_directions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["preferences_id"],
            ["plan_preferences.id"],
            name=op.f("fk_preference_directions_preferences_id_plan_preferences"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("preferences_id", "direction_id", name=op.f("pk_preference_directions")),
    )
    op.create_index(
        op.f("ix_preference_directions_direction_id"), "preference_directions", ["direction_id"], unique=False
    )

    op.create_table(
        "trimester_loads",
        sa.Column("preferences_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column(
            "trimester",
            sa.Enum(
                "autumn", "spring", "summer", name="trimester", native_enum=False, create_constraint=True, length=32
            ),
            nullable=False,
        ),
        sa.Column(
            "load_level",
            sa.Enum("low", "medium", "high", name="load_level", native_enum=False, create_constraint=True, length=32),
            nullable=False,
        ),
        sa.Column("is_auto", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["preferences_id"],
            ["plan_preferences.id"],
            name=op.f("fk_trimester_loads_preferences_id_plan_preferences"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("preferences_id", "trimester", name=op.f("pk_trimester_loads")),
    )
    op.create_table(
        "academic_records",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(always=False), nullable=False
        ),
        sa.Column("student_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("academic_year", sa.SmallInteger(), nullable=False),
        sa.Column("course_year", sa.SmallInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("credits", sa.Numeric(precision=4, scale=1, asdecimal=False), nullable=False),
        sa.Column(
            "trimester",
            sa.Enum(
                "autumn", "spring", "summer", name="trimester", native_enum=False, create_constraint=True, length=32
            ),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.Enum(
                "normative",
                "professional",
                "free_choice",
                name="academic_category",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum(
                "self_declared",
                "deanery_document",
                "approved_plan",
                "admin",
                "saz_sync",
                name="record_source",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("verified_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("plan_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("course_year BETWEEN 1 AND 4", name=op.f("ck_academic_records_course_year_range")),
        sa.CheckConstraint("credits > 0", name=op.f("ck_academic_records_credits_positive")),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name=op.f("fk_academic_records_course_id_courses"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["deanery_plan_documents.id"],
            name=op.f("fk_academic_records_document_id_deanery_plan_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["individual_plans.id"],
            name=op.f("fk_academic_records_plan_id_individual_plans"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["users.id"], name=op.f("fk_academic_records_student_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["verified_by"], ["users.id"], name=op.f("fk_academic_records_verified_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_academic_records")),
        sa.UniqueConstraint("student_id", "course_id", name=op.f("uq_academic_records_student_id_course_id")),
    )
    op.create_index(op.f("ix_academic_records_document_id"), "academic_records", ["document_id"], unique=False)

    op.create_table(
        "course_directions",
        sa.Column("course_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("direction_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name=op.f("fk_course_directions_course_id_courses"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["direction_id"],
            ["directions.id"],
            name=op.f("fk_course_directions_direction_id_directions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("course_id", "direction_id", name=op.f("pk_course_directions")),
    )
    op.create_index(op.f("ix_course_directions_direction_id"), "course_directions", ["direction_id"], unique=False)

    op.create_table(
        "course_instructors",
        sa.Column("course_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("instructor_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "lecturer", "practice", name="instructor_role", native_enum=False, create_constraint=True, length=32
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name=op.f("fk_course_instructors_course_id_courses"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["instructor_id"],
            ["instructors.id"],
            name=op.f("fk_course_instructors_instructor_id_instructors"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("course_id", "instructor_id", name=op.f("pk_course_instructors")),
    )
    op.create_table(
        "moderation_items",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(always=False), nullable=False
        ),
        sa.Column("sync_job_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("course_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column(
            "change_type",
            sa.Enum(
                "add",
                "update",
                "remove",
                name="moderation_change_type",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "payload", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False
        ),
        sa.Column("diff", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                name="moderation_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("reviewed_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name=op.f("fk_moderation_items_course_id_courses"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"], ["users.id"], name=op.f("fk_moderation_items_reviewed_by_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["sync_job_id"],
            ["sync_jobs.id"],
            name=op.f("fk_moderation_items_sync_job_id_sync_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_moderation_items")),
    )
    op.create_index("ix_moderation_items_status_job", "moderation_items", ["status", "sync_job_id"], unique=False)

    op.create_table(
        "normative_course_entries",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(always=False), nullable=False
        ),
        sa.Column("document_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("course_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("raw_title", sa.String(length=300), nullable=False),
        sa.Column("credits", sa.Numeric(precision=4, scale=1, asdecimal=False), nullable=False),
        sa.Column(
            "trimester",
            sa.Enum(
                "autumn", "spring", "summer", name="trimester", native_enum=False, create_constraint=True, length=32
            ),
            nullable=False,
        ),
        sa.CheckConstraint("credits > 0", name=op.f("ck_normative_course_entries_credits_positive")),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_normative_course_entries_course_id_courses"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["deanery_plan_documents.id"],
            name=op.f("fk_normative_course_entries_document_id_deanery_plan_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_normative_course_entries")),
    )
    op.create_index(
        op.f("ix_normative_course_entries_document_id"), "normative_course_entries", ["document_id"], unique=False
    )

    op.create_table(
        "plan_items",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.Identity(always=False), nullable=False
        ),
        sa.Column("plan_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("course_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column(
            "trimester",
            sa.Enum(
                "autumn", "spring", "summer", name="trimester", native_enum=False, create_constraint=True, length=32
            ),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.Enum(
                "professional",
                "free_choice",
                name="plan_item_category",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name=op.f("fk_plan_items_course_id_courses"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["individual_plans.id"],
            name=op.f("fk_plan_items_plan_id_individual_plans"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_items")),
        sa.UniqueConstraint("plan_id", "course_id", name=op.f("uq_plan_items_plan_id_course_id")),
    )
    op.create_index(op.f("ix_plan_items_course_id"), "plan_items", ["course_id"], unique=False)

    if op.get_bind().dialect.name == "postgresql":
        # SEC-001: журнал аудиту лише доповнюється
        op.execute("""
            CREATE FUNCTION audit_log_append_only() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_log is append-only';
            END;
            $$ LANGUAGE plpgsql
            """)
        op.execute(
            "CREATE TRIGGER audit_log_append_only BEFORE UPDATE OR DELETE ON audit_log "
            "FOR EACH ROW EXECUTE FUNCTION audit_log_append_only()"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_log_append_only ON audit_log")
        op.execute("DROP FUNCTION IF EXISTS audit_log_append_only()")
    op.drop_index(op.f("ix_plan_items_course_id"), table_name="plan_items")
    op.drop_table("plan_items")
    op.drop_index(op.f("ix_normative_course_entries_document_id"), table_name="normative_course_entries")
    op.drop_table("normative_course_entries")
    op.drop_index("ix_moderation_items_status_job", table_name="moderation_items")
    op.drop_table("moderation_items")
    op.drop_table("course_instructors")
    op.drop_index(op.f("ix_course_directions_direction_id"), table_name="course_directions")
    op.drop_table("course_directions")
    op.drop_index(op.f("ix_academic_records_document_id"), table_name="academic_records")
    op.drop_table("academic_records")
    op.drop_table("trimester_loads")
    op.drop_index(op.f("ix_preference_directions_direction_id"), table_name="preference_directions")
    op.drop_table("preference_directions")
    op.drop_index(op.f("ix_instructor_preferences_instructor_id"), table_name="instructor_preferences")
    op.drop_table("instructor_preferences")
    op.drop_index("ix_individual_plans_student_year", table_name="individual_plans")
    op.drop_index("ix_individual_plans_student_status", table_name="individual_plans")
    op.drop_table("individual_plans")
    op.drop_index(op.f("ix_courses_title_normalized"), table_name="courses")
    op.drop_table("courses")
    op.drop_index(
        "uq_sync_jobs_active_source",
        table_name="sync_jobs",
        postgresql_where=sa.text("status IN ('queued', 'running')"),
        sqlite_where=sa.text("status IN ('queued', 'running')"),
    )
    op.drop_index("ix_sync_jobs_started_at", table_name="sync_jobs")
    op.drop_table("sync_jobs")
    op.drop_table("student_profiles")
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_table("plan_preferences")
    op.drop_table("deanery_plan_documents")
    op.drop_index("ix_audit_log_object", table_name="audit_log")
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_actor_id"), table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("users")
    op.drop_index(op.f("ix_instructors_full_name_normalized"), table_name="instructors")
    op.drop_table("instructors")
    op.drop_table("directions")
