"""
Тести блокування міграцій (pg_advisory_lock) при старті застосунку (issue #218).

Використання ШІ: файл створено за допомогою Antigravity (Claude Sonnet 4.6, Google DeepMind) для issue #218.
Перевірено: pytest tests/test_migrate_lock.py.
"""

from unittest.mock import MagicMock

from src.db.migrate import migration_lock


def test_migration_lock_noop_on_sqlite():
    mock_engine = MagicMock()
    mock_engine.dialect.name = "sqlite"

    entered = False
    with migration_lock(mock_engine):
        entered = True

    assert entered is True
    mock_engine.connect.assert_not_called()


def test_migration_lock_acquires_and_releases_on_postgres():
    mock_engine = MagicMock()
    mock_engine.dialect.name = "postgresql"
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with migration_lock(mock_engine):
        pass

    calls = mock_conn.execute.call_args_list
    assert len(calls) == 2
    assert "pg_advisory_lock" in str(calls[0].args[0])
    assert "pg_advisory_unlock" in str(calls[1].args[0])
    assert mock_conn.commit.call_count == 2
