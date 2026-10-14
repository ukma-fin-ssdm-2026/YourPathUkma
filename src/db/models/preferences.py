"""
Побажання студента на рік: plan_preferences, preference_directions, trimester_loads, instructor_preferences.

Використання ШІ: файл створено за допомогою Claude (Claude Code) за data-model.md і contract.md §3.2.3.
Перевірка: pytest, `alembic check`.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, Identity, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, BigIntId, UTCDateTime, db_enum, utcnow
from ..enums import InstructorPreferenceKind, LoadLevel, Trimester


class PreferenceDirection(Base):
    """1–3 напрямки на побажання (FR-007); кількість перевіряє сервер."""

    __tablename__ = "preference_directions"

    preferences_id: Mapped[int] = mapped_column(
        BigIntId, ForeignKey("plan_preferences.id", ondelete="CASCADE"), primary_key=True
    )
    direction_id: Mapped[int] = mapped_column(
        BigIntId, ForeignKey("directions.id", ondelete="RESTRICT"), primary_key=True, index=True
    )


class TrimesterLoad(Base):
    __tablename__ = "trimester_loads"

    preferences_id: Mapped[int] = mapped_column(
        BigIntId, ForeignKey("plan_preferences.id", ondelete="CASCADE"), primary_key=True
    )
    trimester: Mapped[Trimester] = mapped_column(db_enum(Trimester, "trimester"), primary_key=True)
    load_level: Mapped[LoadLevel] = mapped_column(db_enum(LoadLevel, "load_level"))
    is_auto: Mapped[bool] = mapped_column(Boolean, default=False)  # true для 4 курсу (FR-003)


class InstructorPreference(Base):
    """
    Бажаний / небажаний викладач (FR-005). Складений PK не дає викладачу бути в обох списках одночасно.
    Список небажаних чутливий (R1): лише власнику, ніколи в LLM.
    """

    __tablename__ = "instructor_preferences"

    preferences_id: Mapped[int] = mapped_column(
        BigIntId, ForeignKey("plan_preferences.id", ondelete="CASCADE"), primary_key=True
    )
    instructor_id: Mapped[int] = mapped_column(
        BigIntId, ForeignKey("instructors.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    kind: Mapped[InstructorPreferenceKind] = mapped_column(
        db_enum(InstructorPreferenceKind, "instructor_preference_kind")
    )


class PlanPreferences(Base):
    """Побажання на навчальний рік; один запис на (студент, рік), PUT /preferences/{year} його замінює."""

    __tablename__ = "plan_preferences"
    __table_args__ = (UniqueConstraint("student_id", "academic_year"),)

    id: Mapped[int] = mapped_column(BigIntId, Identity(), primary_key=True)
    student_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("users.id", ondelete="CASCADE"))
    academic_year: Mapped[int] = mapped_column(SmallInteger)  # рік початку: 2026 = 2026/2027
    include_free_electives: Mapped[bool] = mapped_column(Boolean, default=True)
    wants_certificate: Mapped[bool] = mapped_column(Boolean, default=False)
    # FK на certificate_programs з'явиться разом із таблицею на етапі 2
    certificate_program_id: Mapped[Optional[int]] = mapped_column(BigIntId)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    directions: Mapped[List[PreferenceDirection]] = relationship(cascade="all, delete-orphan")
    trimester_loads: Mapped[List[TrimesterLoad]] = relationship(cascade="all, delete-orphan")
    instructor_preferences: Mapped[List[InstructorPreference]] = relationship(cascade="all, delete-orphan")
