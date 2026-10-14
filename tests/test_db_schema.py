"""
Тести схеми БД: міграції збігаються з моделями, обмеження цілісності працюють на рівні БД.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest на SQLite і PostgreSQL.
"""

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from src.db.enums import AuditOutcome, SyncInitiator, SyncJobStatus, SyncSource
from src.db.migrate import alembic_config
from src.db.models import AuditLog, IndividualPlan, PlanItem, SyncJob
from src.db.session import session_factory


def test_migrations_match_models():
    # Падає, якщо моделі змінено без нової міграції (alembic revision --autogenerate)
    command.check(alembic_config())


def test_only_one_active_sync_job_per_source():
    with session_factory()() as db:
        db.add(SyncJob(source=SyncSource.SAZ_CATALOG, initiator=SyncInitiator.ADMIN, initiated_by=1))
        db.add(SyncJob(source=SyncSource.FACULTY_CERTIFICATES, initiator=SyncInitiator.SCHEDULER))
        db.flush()
        db.add(SyncJob(source=SyncSource.SAZ_CATALOG, initiator=SyncInitiator.SCHEDULER))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


def test_finished_sync_job_does_not_block_new_one():
    with session_factory()() as db:
        db.add(SyncJob(source=SyncSource.SAZ_CATALOG, initiator=SyncInitiator.ADMIN, status=SyncJobStatus.FAILED))
        db.add(SyncJob(source=SyncSource.SAZ_CATALOG, initiator=SyncInitiator.ADMIN))
        db.flush()
        db.rollback()


def test_plan_item_requires_existing_course():
    with session_factory()() as db:
        plan = db.get(IndividualPlan, 1)
        db.add(PlanItem(plan_id=plan.id, course_id=999999, trimester="autumn", category="professional"))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


def test_deleting_plan_cascades_to_items():
    with session_factory()() as db:
        db.execute(text("DELETE FROM individual_plans WHERE id = 3"))
        assert db.scalar(text("SELECT COUNT(*) FROM plan_items WHERE plan_id = 3")) == 0
        db.rollback()


def test_audit_log_is_append_only_on_postgres():
    with session_factory()() as db:
        if db.get_bind().dialect.name != "postgresql":
            pytest.skip("Тригер append-only є лише в PostgreSQL")
        db.add(
            AuditLog(
                actor_id=42,
                action="plan.read",
                object_type="IndividualPlan",
                object_id=3,
                outcome=AuditOutcome.DENIED,
                ip="10.0.0.15",
            )
        )
        db.flush()
        with pytest.raises(DBAPIError):
            db.execute(text("UPDATE audit_log SET action = 'x'"))
        db.rollback()
