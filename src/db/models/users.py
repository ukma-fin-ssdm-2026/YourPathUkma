"""
Користувачі та профілі: users, student_profiles, refresh_tokens.

Використання ШІ: файл створено за допомогою Claude (Claude Code) за data-model.md («Users & Profiles»)
і contract.md §3.1–3.2. Перевірка: pytest, `alembic check`.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Identity, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, BigIntId, UTCDateTime, db_enum, utcnow
from ..enums import CourseYearSource, UserRole


class User(Base):
    """Обліковий запис після Microsoft SSO (студент або адмін). Роль — лише з БД, не з клієнта (R2)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigIntId, Identity(), primary_key=True)
    google_sub: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)  # зберігається в нижньому регістрі
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(db_enum(UserRole, "user_role"), default=UserRole.STUDENT)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())

    student_profile: Mapped[Optional["StudentProfile"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )


class StudentProfile(Base):
    """
    Профіль студента (1:1 з User). `course_year` і `specialty` порожні до онбордингу (contract.md §3.2.1).
    Лічильники кредитів (…/240, …/25, …/54) не зберігаються: сервер рахує їх з academic_records (R15).
    """

    __tablename__ = "student_profiles"
    __table_args__ = (CheckConstraint("course_year BETWEEN 1 AND 4", name="course_year_range"),)

    user_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    faculty: Mapped[str] = mapped_column(String(100), default="ФІ")
    specialty: Mapped[Optional[str]] = mapped_column(String(150))
    course_year: Mapped[Optional[int]] = mapped_column(SmallInteger)
    course_year_source: Mapped[Optional[CourseYearSource]] = mapped_column(
        db_enum(CourseYearSource, "course_year_source")
    )
    saz_synced_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())

    user: Mapped[User] = relationship(back_populates="student_profile")


class RefreshToken(Base):
    """
    Refresh-токени для ротації і відкликання (/auth/refresh, /auth/logout). Зберігається лише SHA-256 токена,
    сам токен живе тільки в cookie HttpOnly (R7).
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(BigIntId, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    revoked_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
