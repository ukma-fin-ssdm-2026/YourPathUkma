"""
Індивідуальні плани: individual_plans, plan_items.

Використання ШІ: файл створено за допомогою Claude (Claude Code) за data-model.md («Individual Plans»)
і contract.md §3.4. Перевірка: pytest (CRUD планів через API), `alembic check`.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index, Numeric, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, BigIntId, Credits, UTCDateTime, db_enum, utcnow
from ..enums import LoadLevel, PlanItemCategory, PlanOrigin, PlanStatus, Trimester
from .catalog import Course


class PlanItem(Base):
    """
    Вибіркова дисципліна плану. Назва і кредити не дублюються: беруться з courses за course_id.
    Нормативні дисципліни сюди не потрапляють (вони в normative_course_entries), це перевіряє сервер.
    """

    __tablename__ = "plan_items"
    __table_args__ = (UniqueConstraint("plan_id", "course_id"),)

    id: Mapped[int] = mapped_column(BigIntId, Identity(), primary_key=True)
    plan_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("individual_plans.id", ondelete="CASCADE"))
    # RESTRICT: дисципліну з планів не видаляють, а архівують (publication_status)
    course_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    trimester: Mapped[Trimester] = mapped_column(db_enum(Trimester, "trimester"))
    category: Mapped[PlanItemCategory] = mapped_column(db_enum(PlanItemCategory, "plan_item_category"))

    course: Mapped[Course] = relationship(lazy="joined")


class IndividualPlan(Base):
    """
    План студента на навчальний рік. `total_credits` перераховує сервер при кожному збереженні.
    Рівні навантаження зберігаються в плані (PUT /plans замінює їх разом з items); trimester_loads
    стосуються лише побажань.
    """

    __tablename__ = "individual_plans"
    __table_args__ = (
        CheckConstraint("course_year BETWEEN 2 AND 4", name="course_year_range"),
        CheckConstraint("total_credits >= 0", name="total_credits_non_negative"),
        Index("ix_individual_plans_student_status", "student_id", "status"),
        Index("ix_individual_plans_student_year", "student_id", "academic_year"),
    )

    id: Mapped[int] = mapped_column(BigIntId, Identity(), primary_key=True)
    student_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("users.id", ondelete="CASCADE"))
    academic_year: Mapped[int] = mapped_column(SmallInteger)  # рік початку: 2026 = 2026/2027
    course_year: Mapped[int] = mapped_column(SmallInteger)  # `course` в API
    title: Mapped[Optional[str]] = mapped_column(String(200))
    status: Mapped[PlanStatus] = mapped_column(db_enum(PlanStatus, "plan_status"), default=PlanStatus.DRAFT)
    origin: Mapped[PlanOrigin] = mapped_column(db_enum(PlanOrigin, "plan_origin"), default=PlanOrigin.MANUAL)
    load_autumn: Mapped[LoadLevel] = mapped_column(db_enum(LoadLevel, "load_autumn"), default=LoadLevel.MEDIUM)
    load_spring: Mapped[LoadLevel] = mapped_column(db_enum(LoadLevel, "load_spring"), default=LoadLevel.MEDIUM)
    load_summer: Mapped[LoadLevel] = mapped_column(db_enum(LoadLevel, "load_summer"), default=LoadLevel.MEDIUM)
    total_credits: Mapped[float] = mapped_column(Numeric(5, 1, asdecimal=False), default=0)
    preferences_id: Mapped[Optional[int]] = mapped_column(
        BigIntId, ForeignKey("plan_preferences.id", ondelete="SET NULL")
    )
    # Видалення документа, прив'язаного до не-чернетки, забороняє сервер (409 DOCUMENT_IN_USE)
    deanery_document_id: Mapped[Optional[int]] = mapped_column(
        BigIntId, ForeignKey("deanery_plan_documents.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    items: Mapped[List[PlanItem]] = relationship(cascade="all, delete-orphan", order_by=PlanItem.id, lazy="selectin")
