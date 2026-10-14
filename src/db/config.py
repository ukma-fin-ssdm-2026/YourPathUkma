"""
Адреса БД з оточення.

DATABASE_URL — основна змінна (PostgreSQL у Docker/на хостингу). Без неї використовується локальний файл
SQLite у корені репозиторію: так `uvicorn src.api.main:app` запускається без Docker.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest на SQLite і PostgreSQL.
"""

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_URL = f"sqlite:///{ROOT_DIR / 'yourpath.sqlite'}"


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip() or DEFAULT_SQLITE_URL
    # Render/Railway видають postgres:// або postgresql:// — у проєкті встановлено лише драйвер psycopg (v3)
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url
