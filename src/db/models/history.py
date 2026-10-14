"""
Академічна історія студента: academic_records (contract.md §3.2.2).

Сутності немає в data-model.md: вона з'явилась у контракті, бо синхронізація з САЗ заблокована (R14),
а лічильники кредитів, ліміт 25 за всі роки і перевірка 240 потребують даних про попередні роки.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest, `alembic check`.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Identity, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, BigIntId, Credits, UTCDateTime, db_enum, utcnow
from ..enums import AcademicCategory, RecordSource, Trimester


class AcademicRecord(Base):
    """
    Пройдена дисципліна. `title` і `credits` зберігаються завжди: дисципліну могли прибрати з каталогу.
    Унікальність (student_id, course_id) не дає двічі зарахувати ту саму дисципліну; NULL не конфліктують.
    """

    __tablename__ = "academic_records"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id"),
        CheckConstraint("course_year BETWEEN 1 AND 4", name="course_year_range"),
        CheckConstraint("credits > 0", name="credits_positive"),
    )

    id: Mapped[int] = mapped_column(BigIntId, Identity(), primary_key=True)
    student_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("users.id", ondelete="CASCADE"))
    academic_year: Mapped[int] = mapped_column(SmallInteger)
    course_year: Mapped[int] = mapped_column(SmallInteger)
    course_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("courses.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(300))
    credits: Mapped[float] = mapped_column(Credits)
    trimester: Mapped[Trimester] = mapped_column(db_enum(Trimester, "trimester"))
    category: Mapped[AcademicCategory] = mapped_column(db_enum(AcademicCategory, "academic_category"))
    source: Mapped[RecordSource] = mapped_column(db_enum(RecordSource, "record_source"))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("users.id", ondelete="SET NULL"))
    verified_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    # Записи з документа деканату видаляються разом із ним (contract.md §3.6, DELETE)
    document_id: Mapped[Optional[int]] = mapped_column(
        BigIntId, ForeignKey("deanery_plan_documents.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("individual_plans.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
