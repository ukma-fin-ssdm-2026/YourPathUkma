"""
Середовище Alembic. Метадані — з src.db.models, адреса БД — з DATABASE_URL (або передана з src/db/migrate.py).

Використання ШІ: файл створено за допомогою Claude (Claude Code) на основі стандартного шаблону Alembic.
Перевірка: alembic upgrade/downgrade/check на SQLite і PostgreSQL.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from src.db import models  # noqa: F401  (реєструє таблиці в Base.metadata)
from src.db.base import Base
from src.db.config import database_url

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", database_url().replace("%", "%%"))

target_metadata = Base.metadata


def _configure(**kwargs) -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        target_metadata=target_metadata,
        compare_type=True,
        # SQLite не вміє ALTER COLUMN: Alembic перебудовує таблицю (batch mode)
        render_as_batch=url.startswith("sqlite"),
        **kwargs,
    )


def run_migrations_offline() -> None:
    _configure(url=config.get_main_option("sqlalchemy.url"), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
