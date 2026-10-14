"""
Каталог: courses, instructors, course_instructors, directions, course_directions.

Використання ШІ: файл створено за допомогою Claude (Claude Code) за data-model.md («Courses & Catalogs»)
і contract.md §3.3, §3.5. Перевірка: pytest, `alembic check`.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import CheckConstraint, ForeignKey, Identity, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, BigIntId, Credits, UTCDateTime, db_enum, utcnow
from ..enums import CourseKind, InstructorRole, PublicationStatus, Trimester


class Direction(Base):
    """Напрямок розвитку. `name` — те саме значення, що в Discipline.directions і фільтрі каталогу."""

    __tablename__ = "directions"

    id: Mapped[int] = mapped_column(BigIntId, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    # Унікальність без урахування регістру (contract.md §3.9, DIRECTION_NAME_TAKEN)
    name_normalized: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)


class Instructor(Base):
    __tablename__ = "instructors"

    id: Mapped[int] = mapped_column(BigIntId, Identity(), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200))
    full_name_normalized: Mapped[str] = mapped_column(String(200), index=True)


class CourseInstructor(Base):
    __tablename__ = "course_instructors"

    course_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
    instructor_id: Mapped[int] = mapped_column(
        BigIntId, ForeignKey("instructors.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[InstructorRole] = mapped_column(
        db_enum(InstructorRole, "instructor_role"), default=InstructorRole.LECTURER
    )

    instructor: Mapped[Instructor] = relationship(lazy="joined")


class CourseDirection(Base):
    """Профорієнтовність: дисципліна профорієнтовна для напрямку. Напрямок у використанні не видаляється."""

    __tablename__ = "course_directions"

    course_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
    direction_id: Mapped[int] = mapped_column(
        BigIntId, ForeignKey("directions.id", ondelete="RESTRICT"), primary_key=True, index=True
    )


class Course(Base):
    """
    Дисципліна з каталогу САЗ. `id` — те саме значення, що Discipline.id і PlanItem.course_id в API.
    Нові та змінені дисципліни потрапляють сюди лише через схвалений moderation_item (ADR-002).
    """

    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint("credits > 0", name="credits_positive"),
        CheckConstraint("recommended_year BETWEEN 1 AND 4", name="recommended_year_range"),
    )

    id: Mapped[int] = mapped_column(BigIntId, Identity(), primary_key=True)
    saz_code: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    title_normalized: Mapped[str] = mapped_column(String(300), index=True)  # звірка сертифікатних програм
    description: Mapped[str] = mapped_column(Text, default="")  # недовірений вміст із САЗ
    credits: Mapped[float] = mapped_column(Credits)
    trimester: Mapped[Trimester] = mapped_column(db_enum(Trimester, "trimester"))
    recommended_year: Mapped[int] = mapped_column(SmallInteger)
    kind: Mapped[CourseKind] = mapped_column(db_enum(CourseKind, "course_kind"))
    publication_status: Mapped[PublicationStatus] = mapped_column(
        db_enum(PublicationStatus, "publication_status"), default=PublicationStatus.PUBLISHED
    )
    last_sync_job_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("sync_jobs.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    course_instructors: Mapped[List[CourseInstructor]] = relationship(
        cascade="all, delete-orphan", order_by=CourseInstructor.instructor_id
    )
    directions: Mapped[List[Direction]] = relationship(secondary="course_directions", order_by=Direction.id)
