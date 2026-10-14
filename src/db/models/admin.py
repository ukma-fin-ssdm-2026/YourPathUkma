"""
Адміністрування: sync_jobs, moderation_items, audit_log.

Використання ШІ: файл створено за допомогою Claude (Claude Code) за data-model.md («Moderation Queue & SyncJobs»,
«Audit»), ADR-002 і contract.md §3.9. Перевірка: pytest (зокрема обмеження «одна активна задача на джерело»),
`alembic check`.
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import ForeignKey, Identity, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, BigIntId, IpAddress, JsonDoc, UTCDateTime, db_enum, utcnow
from ..enums import AuditOutcome, ModerationChangeType, ModerationStatus, SyncInitiator, SyncJobStatus, SyncSource

_ACTIVE_JOB = text("status IN ('queued', 'running')")


class SyncJob(Base):
    """
    Запуск парсингу САЗ або сайту сертифікатів (FR-008, FR-011).
    Частковий унікальний індекс: на джерело не більше однієї задачі в статусі queued/running (R4,
    409 SYNC_JOB_ALREADY_RUNNING) — гарантія на рівні БД навіть при одночасних запитах.
    """

    __tablename__ = "sync_jobs"
    __table_args__ = (
        Index(
            "uq_sync_jobs_active_source",
            "source",
            unique=True,
            postgresql_where=_ACTIVE_JOB,
            sqlite_where=_ACTIVE_JOB,
        ),
        Index("ix_sync_jobs_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(BigIntId, Identity(), primary_key=True)
    source: Mapped[SyncSource] = mapped_column(db_enum(SyncSource, "sync_source"))
    initiator: Mapped[SyncInitiator] = mapped_column(db_enum(SyncInitiator, "sync_initiator"))
    initiated_by: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[SyncJobStatus] = mapped_column(
        db_enum(SyncJobStatus, "sync_job_status"), default=SyncJobStatus.QUEUED
    )
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    added_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    # Сирий HTML для розбору збоїв парсера (R13); в API не повертається
    raw_snapshot: Mapped[Optional[str]] = mapped_column(Text, deferred=True)
    raw_snapshot_sha256: Mapped[Optional[str]] = mapped_column(String(64))


class ModerationItem(Base):
    """Зміна каталогу від парсера, що чекає рішення адміна (ADR-002). У courses потрапляє лише після approve."""

    __tablename__ = "moderation_items"
    __table_args__ = (Index("ix_moderation_items_status_job", "status", "sync_job_id"),)

    id: Mapped[int] = mapped_column(BigIntId, Identity(), primary_key=True)
    sync_job_id: Mapped[int] = mapped_column(BigIntId, ForeignKey("sync_jobs.id", ondelete="CASCADE"))
    course_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("courses.id", ondelete="SET NULL"))
    change_type: Mapped[ModerationChangeType] = mapped_column(db_enum(ModerationChangeType, "moderation_change_type"))
    payload: Mapped[dict[str, Any]] = mapped_column(JsonDoc)
    diff: Mapped[Optional[dict[str, Any]]] = mapped_column(JsonDoc)
    status: Mapped[ModerationStatus] = mapped_column(
        db_enum(ModerationStatus, "moderation_status"), default=ModerationStatus.PENDING
    )
    reviewed_by: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime())
    review_reason: Mapped[Optional[str]] = mapped_column(Text)  # необов'язкова причина reject
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class AuditLog(Base):
    """
    Журнал доступу і змін (SEC-001), append-only. У PostgreSQL UPDATE/DELETE блокує тригер з міграції.
    Через це actor_id без ON DELETE: користувача з записами в журналі видалити не можна.
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_created_at", "created_at"),
        Index("ix_audit_log_object", "object_type", "object_id"),
    )

    id: Mapped[int] = mapped_column(BigIntId, Identity(), primary_key=True)
    actor_id: Mapped[Optional[int]] = mapped_column(BigIntId, ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(64))  # plan.read, user.update, moderation.approve, ...
    object_type: Mapped[str] = mapped_column(String(64))
    object_id: Mapped[Optional[int]] = mapped_column(BigIntId)
    outcome: Mapped[AuditOutcome] = mapped_column(db_enum(AuditOutcome, "audit_outcome"))
    old_value: Mapped[Optional[dict[str, Any]]] = mapped_column(JsonDoc)
    new_value: Mapped[Optional[dict[str, Any]]] = mapped_column(JsonDoc)
    ip: Mapped[Optional[str]] = mapped_column(IpAddress)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
