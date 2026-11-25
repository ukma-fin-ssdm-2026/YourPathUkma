"""
Інтеграційні тести зі справжньою залежністю: PostgreSQL 16 у контейнері (service container у GitHub Actions).

Набір повільний (маркер `slow`): на pull request не запускається, а працює після злиття в `main`.
На SQLite ці перевірки неможливі: там немає ні справжніх блокувань рядків, ні серверної версії, ні типів PostgreSQL.
У CI змінна REQUIRE_POSTGRES=1 перетворює пропуск на помилку, щоб набір не став «зеленим» без бази.

Використання ШІ: файл створено за допомогою Claude (Anthropic), доповнено Antigravity (Claude Sonnet 4.6,
Google DeepMind) тестом pg_advisory_lock для міграцій (issue #218).
"""

import os

import pytest
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError

from src.api.main import app
from src.db.migrate import alembic_config
from src.db.models import User
from src.db.session import get_engine

pytestmark = pytest.mark.slow

STUDENT_ID = 42  # студент із demo seed (див. tests/conftest.py)
LOCK_NOT_AVAILABLE = "55P03"


@pytest.fixture(scope="module")
def pg_engine():
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        if os.getenv("REQUIRE_POSTGRES") == "1":
            pytest.fail("REQUIRE_POSTGRES=1, але TEST_DATABASE_URL не вказує на PostgreSQL")
        pytest.skip("Потрібен справжній PostgreSQL (TEST_DATABASE_URL)")
    return engine


def test_server_is_real_postgres_16(pg_engine):
    with pg_engine.connect() as connection:
        version = connection.scalar(text("SHOW server_version"))
    assert version.split(".")[0] == "16"


def test_database_schema_is_at_alembic_head(pg_engine):
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    with pg_engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    assert current == head


def test_row_lock_is_enforced_by_server(pg_engine):
    """Другий клієнт не отримує рядок, який заблоковано першою транзакцією (FOR UPDATE NOWAIT → SQLSTATE 55P03)."""
    lock_row = select(User.id).where(User.id == STUDENT_ID).with_for_update(nowait=True)
    with pg_engine.connect() as holder, pg_engine.connect() as contender:
        assert holder.scalar(lock_row) == STUDENT_ID
        with pytest.raises(OperationalError) as error:
            contender.execute(lock_row)
        assert error.value.orig.sqlstate == LOCK_NOT_AVAILABLE
        contender.rollback()
        holder.rollback()
        # після завершення першої транзакції рядок знову доступний
        assert contender.scalar(lock_row) == STUDENT_ID
        contender.rollback()


def test_api_reads_catalog_stored_in_postgres(pg_engine):
    with pg_engine.connect() as connection:
        users = connection.scalar(select(func.count()).select_from(User))
    assert users > 0
    response = TestClient(app).get("/api/v1/disciplines", headers={"Authorization": "Bearer test"})
    assert response.status_code == 200
    assert "disciplines" in response.json()


def test_migration_advisory_lock_blocks_contender(pg_engine):
    """Поки migration_lock утримується, інший процес бачить pg_try_advisory_lock = False (issue #218)."""
    from src.db.migrate import MIGRATION_ADVISORY_LOCK_ID, migration_lock

    with migration_lock(pg_engine):
        with pg_engine.connect() as contender:
            acquired = contender.scalar(text("SELECT pg_try_advisory_lock(:id)"), {"id": MIGRATION_ADVISORY_LOCK_ID})
            assert acquired is False
            contender.rollback()

    # Після виходу з контексту блокування звільнено
    with pg_engine.connect() as contender:
        acquired = contender.scalar(text("SELECT pg_try_advisory_lock(:id)"), {"id": MIGRATION_ADVISORY_LOCK_ID})
        assert acquired is True
        contender.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": MIGRATION_ADVISORY_LOCK_ID})
        contender.commit()
