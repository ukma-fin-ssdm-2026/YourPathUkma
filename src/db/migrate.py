"""
Програмний запуск міграцій Alembic (старт застосунку, тести). З командного рядка: `alembic upgrade head`.

Використання ШІ: файл створено за допомогою Claude (Claude Code), доповнено Antigravity (Claude Sonnet 4.6,
Google DeepMind): додано advisory lock навколо міграцій і seed для запобігання race condition
між воркерами (issue #218).
Перевірка: pytest (схема створюється через upgrade head і видаляється через downgrade base на SQLite і PostgreSQL).
"""

import logging
import os
from contextlib import contextmanager
from typing import Iterator

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from .config import ROOT_DIR, database_url
from .seed import seed_demo_data
from .session import get_engine, session_factory

logger = logging.getLogger(__name__)

MIGRATION_ADVISORY_LOCK_ID = 0x596F757250617468  # 6444583907406476392 ("YourPath")


@contextmanager
def migration_lock(engine: Engine | None = None) -> Iterator[None]:
    """
    Блокування для запобігання змаганню (race condition) між воркерами під час старту застосунку (issue #218).
    На PostgreSQL використовує pg_advisory_lock. На інших СУБД (SQLite) — no-op.
    """
    if engine is None:
        try:
            engine = get_engine()
        except Exception:
            yield
            return

    if getattr(engine, "dialect", None) is None or engine.dialect.name != "postgresql":
        yield
        return

    with engine.connect() as conn:
        logger.info("Очікування pg_advisory_lock(%s) для міграцій/seed...", MIGRATION_ADVISORY_LOCK_ID)
        conn.execute(text("SELECT pg_advisory_lock(:id)"), {"id": MIGRATION_ADVISORY_LOCK_ID})
        conn.commit()
        try:
            yield
        finally:
            try:
                conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": MIGRATION_ADVISORY_LOCK_ID})
                conn.commit()
                logger.info("Звільнено pg_advisory_lock(%s)", MIGRATION_ADVISORY_LOCK_ID)
            except Exception as e:
                logger.warning("Не вдалося звільнити pg_advisory_lock: %s", e)


def alembic_config(url: str = "") -> Config:
    config = Config(str(ROOT_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT_DIR / "migrations"))
    # ConfigParser трактує % як інтерполяцію (паролі в URL можуть містити %)
    config.set_main_option("sqlalchemy.url", (url or database_url()).replace("%", "%%"))
    # Не перевизначати логування застосунку налаштуваннями з alembic.ini
    config.attributes["configure_logger"] = False
    return config


def upgrade_head(url: str = "") -> None:
    command.upgrade(alembic_config(url), "head")


def downgrade_base(url: str = "") -> None:
    command.downgrade(alembic_config(url), "base")


def demo_data_enabled() -> bool:
    """
    SEED_DEMO_DATA=1/0 задає це явно. Без неї демо-дані (адмін, студенти, вигадані дисципліни) вмикаються лише
    поза production: на порожній продакшн-БД їх не має бути.
    """
    production = os.getenv("APP_ENV", "development") == "production"
    explicit = os.getenv("SEED_DEMO_DATA")
    if explicit is None:
        return not production
    enabled = explicit == "1"
    if enabled and production:
        logger.warning("SEED_DEMO_DATA=1 при APP_ENV=production: у порожню БД буде додано демо-акаунти й дані")
    return enabled


def init_database() -> None:
    """Виклик при старті API: схема до останньої версії + (за потреби) демо-дані в порожню БД."""
    with migration_lock():
        upgrade_head()
        if demo_data_enabled():
            with session_factory()() as db:
                if seed_demo_data(db):
                    db.commit()
