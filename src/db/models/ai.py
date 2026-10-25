"""
AI-генерація плану: plan_generations, plan_generation_notices (contract.md §3.7).

Генерація асинхронна (R10): POST створює запис зі статусом `pending`, воркер оновлює статус, `plan_id`,
`notices` і `finished_at`. Одна активна генерація на студента гарантується частковим унікальним індексом.

Використання ШІ: файл створено за допомогою Claude за contract.md §3.7 і data-model.md.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index, SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, BigIntId, UTCDateTime, db_enum, utcnow
from ..enums import GenerationStatus


class PlanGenerationNotice(Base):
    """Повідомлення студенту за результатом генерації (напр. UNWANTED_INSTRUCTOR_UNAVOIDABLE, FR-006)."""

    __tablename__ = "plan_generation_notices"

    id: Mapped[int] = mapped_column(BigIntId, Identity(), primary_key=True)
    generation_id: Mapped[int] = mapped_column(
        BigIntId, ForeignKey("plan_generations.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    # SET NULL: дисципліну архівують, але повідомлення про генерацію лишається
    course_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("courses.id", ondelete="SET NULL"))


class PlanGeneration(Base):
    """
    Запит AI-генерації плану. `plan_id` заповнюється при `succeeded`, `error_*` при `failed`.
    Текст prompt не зберігається, лише хеш (R1).
    """

    __tablename__ = "plan_generations"
    __table_args__ = (
        CheckConstraint("attempts BETWEEN 0 AND 3", name="attempts_range"),
        Index("ix_plan_generations_student_created", "student_id", "created_at"),
        # Не більше однієї активної генерації на студента (R10)
        Index(
            "uq_plan_generations_active_student",
            "student_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigIntId, Identity(), primary_key=True)
    student_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("users.id", ondelete="CASCADE"))
    academic_year: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[GenerationStatus] = mapped_column(
        db_enum(GenerationStatus, "generation_status"), default=GenerationStatus.PENDING
    )
    plan_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("individual_plans.id", ondelete="SET NULL"))
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)  # звернень до LLM, ≤ 3 (REL-001)
    prompt_sha256: Mapped[Optional[str]] = mapped_column(String(64))
    error_code: Mapped[Optional[str]] = mapped_column(String(64))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())

    notices: Mapped[List[PlanGenerationNotice]] = relationship(
        cascade="all, delete-orphan", order_by=PlanGenerationNotice.id, lazy="selectin"
    )
