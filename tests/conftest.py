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
os.environ["DATABASE_URL"] = _TEST_DB_URL
# Локальний .env розробника (MS_*, ALLOWED_REDIRECT_URIS…) не має потрапляти в тести
os.environ["SKIP_DOTENV"] = "1"

os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-123456")
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from src.api.common import get_current_student_id  # noqa: E402
from src.api.main import app  # noqa: E402
from src.api.tokens import issue_access_token  # noqa: E402
from src.db import enums as db_enums  # noqa: E402
from src.db.migrate import downgrade_base, upgrade_head  # noqa: E402
from src.db.seed import seed_demo_data  # noqa: E402
from src.db.session import session_factory  # noqa: E402


@pytest.fixture(autouse=True)
def override_auth_dependency(request):
    """Автоматично авторизує тестового студента (ID 42 з seed.py) для всіх тестів,
    окрім тих, що явно тестують відсутність/невалідність токена.
    """
    if (
        "requires_auth" in request.node.name
        or "blank_token" in request.node.name
        or "dev_mode_ignored" in request.node.name
    ):
        yield
        return

    app.dependency_overrides[get_current_student_id] = lambda: 42
    yield
    app.dependency_overrides.pop(get_current_student_id, None)


@pytest.fixture
def auth_headers():
    def factory(user_id: int = 42, role: str = "student"):
        return {"Authorization": f"Bearer {issue_access_token(user_id, role)}"}

    return factory


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
        app.dependency_overrides[get_current_student_id] = lambda: 42
