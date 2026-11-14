"""
Тести налаштувань БД: демо-дані за замовчуванням лише поза production, обов'язковий DATABASE_URL у production,
таймаут підключення до PostgreSQL.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest, ruff check.
"""

import logging

import pytest

from src.db import session as db_session
from src.db.config import database_url
from src.db.migrate import demo_data_enabled


@pytest.fixture
def clean_env(monkeypatch):
    for name in ("APP_ENV", "SEED_DEMO_DATA", "DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_demo_data_enabled_by_default_in_development(clean_env):
    assert demo_data_enabled() is True


def test_demo_data_disabled_by_default_in_production(clean_env):
    clean_env.setenv("APP_ENV", "production")
    assert demo_data_enabled() is False


@pytest.mark.parametrize("env", ["development", "production"])
def test_demo_data_can_be_switched_off_explicitly(clean_env, env):
    clean_env.setenv("APP_ENV", env)
    clean_env.setenv("SEED_DEMO_DATA", "0")
    assert demo_data_enabled() is False


def test_demo_data_forced_on_in_production_is_allowed_but_logged(clean_env, caplog):
    clean_env.setenv("APP_ENV", "production")
    clean_env.setenv("SEED_DEMO_DATA", "1")
    with caplog.at_level(logging.WARNING, logger="src.db.migrate"):
        assert demo_data_enabled() is True
    assert any("SEED_DEMO_DATA=1" in record.getMessage() for record in caplog.records)


def test_database_url_falls_back_to_sqlite_in_development(clean_env):
    assert database_url().startswith("sqlite")


def test_database_url_is_required_in_production(clean_env):
    clean_env.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        database_url()


def test_database_url_in_production_uses_configured_value(clean_env):
    clean_env.setenv("APP_ENV", "production")
    clean_env.setenv("DATABASE_URL", "postgres://user:pw@db.example:5432/app")
    assert database_url() == "postgresql+psycopg://user:pw@db.example:5432/app"


def test_postgres_engine_gets_connect_timeout_and_recycle(clean_env):
    clean_env.setenv("DATABASE_URL", "postgresql://user:pw@db.example:5432/app")
    captured = {}
    clean_env.setattr(db_session, "create_engine", lambda url, **kwargs: captured.update(url=url, **kwargs))

    db_session.get_engine.__wrapped__()  # без lru_cache

    assert captured["connect_args"] == {"connect_timeout": 10}
    assert captured["pool_recycle"] == 1800
    assert captured["pool_pre_ping"] is True
