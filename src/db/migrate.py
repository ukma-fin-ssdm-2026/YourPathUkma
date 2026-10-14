"""
Програмний запуск міграцій Alembic (старт застосунку, тести). З командного рядка: `alembic upgrade head`.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest (схема створюється через
upgrade head і видаляється через downgrade base на SQLite і PostgreSQL).
"""

import os

from alembic import command
from alembic.config import Config

from .config import ROOT_DIR, database_url
from .seed import seed_demo_data
from .session import session_factory


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


def init_database() -> None:
    """
    Виклик при старті API: схема до останньої версії + демо-дані в порожню БД.
    SEED_DEMO_DATA=0 вимикає демо-дані (потрібно, коли з'явиться справжня автентифікація).
    """
    upgrade_head()
    if os.getenv("SEED_DEMO_DATA", "1") == "1":
        with session_factory()() as db:
            if seed_demo_data(db):
                db.commit()
