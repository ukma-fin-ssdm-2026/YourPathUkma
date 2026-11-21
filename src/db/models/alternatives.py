"""
Альтернативні дисципліни до слотів плану: plan_alternatives (FR-009).

Для кожного plan_item AI генерує 2–3 альтернативні дисципліни того ж триместру.
Студент може замінити основну дисципліну на альтернативу; сервер перевіряє ліміти (FR-010).

Використання ШІ: файл створено за допомогою Antigravity (Claude Sonnet 4.6, Google DeepMind)
за requirements.md (FR-009, FR-010) та AGENTS.md §3. Перевірено: pytest, alembic check.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, ForeignKey, Identity, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, BigIntId, db_enum
from ..enums import Trimester
from .catalog import Course

if TYPE_CHECKING:
    from .plans import PlanItem


class PlanAlternative(Base):
    """
    Альтернативна дисципліна для слоту плану (FR-009: 2–3 на слот).
    `plan_item_id` SET NULL при видаленні слоту (альтернативи залишаються як довідкові).
    `course_id` RESTRICT: не видаляти дисципліну з каталогу, поки вона є альтернативою.
    `rank` — порядок переваги від LLM (1 = найкраща).
    """

    __tablename__ = "plan_alternatives"
    __table_args__ = (CheckConstraint("rank BETWEEN 1 AND 3", name="rank_range"),)

    id: Mapped[int] = mapped_column(BigIntId, Identity(), primary_key=True)
    plan_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("individual_plans.id", ondelete="CASCADE"), index=True)
    plan_item_id: Mapped[Optional[int]] = mapped_column(
        BigIntId, ForeignKey("plan_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    course_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    trimester: Mapped[Trimester] = mapped_column(db_enum(Trimester, "trimester"))
    explanation: Mapped[str] = mapped_column(Text, default="")
    rank: Mapped[int] = mapped_column(SmallInteger)  # 1–3

    course: Mapped[Course] = relationship(lazy="joined")
    plan_item: Mapped[Optional[PlanItem]] = relationship(back_populates="alternatives")
