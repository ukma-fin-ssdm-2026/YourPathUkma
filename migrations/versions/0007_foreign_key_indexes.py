"""add missing foreign key indexes (issue #218)

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-21

Використання ШІ: файл створено за допомогою Antigravity (Claude Sonnet 4.6, Google DeepMind) для issue #218.
Перевірено: pytest tests/test_db_schema.py, alembic upgrade head, alembic downgrade 0006.
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_courses_last_sync_job_id", "courses", ["last_sync_job_id"])
    op.create_index("ix_deanery_plan_documents_student_id", "deanery_plan_documents", ["student_id"])
    op.create_index("ix_individual_plans_deanery_document_id", "individual_plans", ["deanery_document_id"])
    op.create_index("ix_moderation_items_course_id", "moderation_items", ["course_id"])


def downgrade() -> None:
    op.drop_index("ix_moderation_items_course_id", table_name="moderation_items")
    op.drop_index("ix_individual_plans_deanery_document_id", table_name="individual_plans")
    op.drop_index("ix_deanery_plan_documents_student_id", table_name="deanery_plan_documents")
    op.drop_index("ix_courses_last_sync_job_id", table_name="courses")
