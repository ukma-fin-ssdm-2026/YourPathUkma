"""
Engine і сесії. Engine створюється при першому зверненні, тому імпорт застосунку (генерація OpenAPI, MCP)
не потребує доступної БД.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest на SQLite і PostgreSQL.
"""

from functools import lru_cache
from typing import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .config import database_url


@lru_cache(maxsize=None)
def get_engine() -> Engine:
    url = database_url()
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _record):
            # У SQLite зовнішні ключі за замовчуванням вимкнені
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    return create_engine(url, pool_pre_ping=True)


@lru_cache(maxsize=None)
def session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI-залежність: одна сесія на запит. Зміни фіксує обробник через db.commit()."""
    with session_factory()() as db:
        yield db
