"""
Спільне налаштування тестів: окрема тестова БД зі свіжою схемою і демо-даними на кожен запуск pytest.

TEST_DATABASE_URL — тестова БД (у CI це PostgreSQL). Без неї використовується тимчасовий файл SQLite.
DATABASE_URL розробника тести навмисно не використовують: схема перед запуском видаляється.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest на SQLite і PostgreSQL.
"""

import os
import tempfile
from pathlib import Path

_TEST_DB_URL = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{Path(tempfile.mkdtemp()) / 'test.sqlite'}"
# Має бути виставлено до першого імпорту src.db.session (engine читає DATABASE_URL один раз)
os.environ["DATABASE_URL"] = _TEST_DB_URL

import pytest  # noqa: E402

from src.db.migrate import downgrade_base, upgrade_head  # noqa: E402
from src.db.seed import seed_demo_data  # noqa: E402
from src.db.session import session_factory  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def test_database():
    downgrade_base()
    upgrade_head()
    with session_factory()() as db:
        seed_demo_data(db)
        db.commit()
    yield _TEST_DB_URL
