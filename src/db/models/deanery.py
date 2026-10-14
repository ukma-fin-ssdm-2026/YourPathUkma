"""
Документи деканату: deanery_plan_documents, normative_course_entries.

Використання ШІ: файл створено за допомогою Claude (Claude Code) за data-model.md («Deanery Documents»)
і contract.md §3.6. Перевірка: pytest, `alembic check`.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Integer, LargeBinary, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, BigIntId, Credits, UTCDateTime, db_enum, utcnow
from ..enums import DocumentMimeType, DocumentParseStatus, Trimester

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


class NormativeCourseEntry(Base):
    """Нормативна дисципліна з документа; `course_id` = null, якщо її не знайдено в каталозі. Лише для читання."""

    __tablename__ = "normative_course_entries"
    __table_args__ = (CheckConstraint("credits > 0", name="credits_positive"),)

    id: Mapped[int] = mapped_column(BigIntId, Identity(), primary_key=True)
    document_id: Mapped[int] = mapped_column(
        BigIntId, ForeignKey("deanery_plan_documents.id", ondelete="CASCADE"), index=True
    )
    course_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("courses.id", ondelete="SET NULL"))
    raw_title: Mapped[str] = mapped_column(String(300))
    credits: Mapped[float] = mapped_column(Credits)
    trimester: Mapped[Trimester] = mapped_column(db_enum(Trimester, "trimester"))


class DeaneryPlanDocument(Base):
    """
    Завантажений документ деканату. Файл зберігається в PostgreSQL (bytea), окремого сховища немає
    (deployment.puml). `content` завантажується лише на вимогу (deferred), щоб списки не тягнули файли.
    """

    __tablename__ = "deanery_plan_documents"
    __table_args__ = (
        CheckConstraint(f"size_bytes > 0 AND size_bytes <= {MAX_DOCUMENT_BYTES}", name="size_bytes_range"),
    )

    id: Mapped[int] = mapped_column(BigIntId, Identity(), primary_key=True)
    student_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("users.id", ondelete="CASCADE"))
    academic_year: Mapped[int] = mapped_column(SmallInteger)
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[DocumentMimeType] = mapped_column(db_enum(DocumentMimeType, "document_mime_type"))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    parse_status: Mapped[DocumentParseStatus] = mapped_column(
        db_enum(DocumentParseStatus, "document_parse_status"), default=DocumentParseStatus.PENDING
    )
    parse_error: Mapped[Optional[str]] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    normative_courses: Mapped[List[NormativeCourseEntry]] = relationship(
        cascade="all, delete-orphan", order_by=NormativeCourseEntry.id
    )
