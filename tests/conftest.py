"""
Спільне налаштування тестів: окрема тестова БД зі свіжою схемою і демо-даними на кожен запуск pytest.

TEST_DATABASE_URL — тестова БД (у CI це PostgreSQL). Без неї використовується тимчасовий файл SQLite.
DATABASE_URL розробника тести навмисно не використовують: схема перед запуском видаляється.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest на SQLite і PostgreSQL.
"""

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

_TEST_DB_URL = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{Path(tempfile.mkdtemp()) / 'test.sqlite'}"
# Має бути виставлено до першого імпорту src.db.session (engine читає DATABASE_URL один раз)
os.environ["DATABASE_URL"] = _TEST_DB_URL

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from src.api.common import get_current_student_id  # noqa: E402
from src.api.main import app  # noqa: E402
from src.db import enums as db_enums  # noqa: E402
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


@pytest.fixture
def fake_session():
    """Підроблена сесія БД: spec=Session не дозволяє викликати методи, яких у Session немає."""
    return MagicMock(spec=Session)


@pytest.fixture
def make_item():
    """Фабрика елементів модерації без БД: зміни за замовчуванням можна перевизначити іменованими аргументами."""

    def factory(**overrides):
        data = {
            "id": 1,
            "change_type": db_enums.ModerationChangeType.UPDATE,
            "payload": {},
            "course_id": 7,
            "sync_job_id": 3,
        }
        data.update(overrides)
        return SimpleNamespace(**data)

    return factory


@pytest.fixture
def admin_client():
    """TestClient від імені адміністратора із seed (id 1); перевизначення залежності знімається після тесту."""
    app.dependency_overrides[get_current_student_id] = lambda: 1
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_student_id, None)
