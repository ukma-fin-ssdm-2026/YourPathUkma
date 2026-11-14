"""
Тести ротації refresh-токена: grace-вікно для майже одночасних запитів (друга вкладка, повтор після втраченої
відповіді) і збереження захисту від викраденого токена та від використання після виходу.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest, ruff check
(тести на цих кроках спершу падали на коді без grace-вікна).
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update

from src.api.auth_service import (
    REFRESH_REUSE_GRACE_SECONDS,
    create_refresh_token,
    hash_token,
    revoke_refresh_token,
    rotate_refresh_token,
)
from src.api.common import ApiError
from src.api.main import app
from src.db.base import utcnow
from src.db.models.users import RefreshToken
from src.db.session import session_factory

STUDENT_ID = 42


@pytest.fixture(autouse=True)
def clean_tokens():
    def wipe():
        with session_factory()() as db:
            db.execute(delete(RefreshToken).where(RefreshToken.user_id == STUDENT_ID))
            db.commit()

    wipe()
    yield
    wipe()


def _issue() -> str:
    with session_factory()() as db:
        raw = create_refresh_token(db, STUDENT_ID)
        db.commit()
    return raw


def _rotate(raw: str) -> str:
    with session_factory()() as db:
        return rotate_refresh_token(db, raw)[1]


def _age_revocation(raw: str, seconds: int) -> None:
    """Імітує, що токен було відкликано `seconds` секунд тому."""
    with session_factory()() as db:
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_sha256 == hash_token(raw))
            .values(revoked_at=utcnow() - timedelta(seconds=seconds))
        )
        db.commit()


def test_rotation_issues_new_token_and_revokes_the_old_one():
    old = _issue()
    new = _rotate(old)

    assert new != old
    with session_factory()() as db:
        row = db.scalar(select(RefreshToken).where(RefreshToken.token_sha256 == hash_token(old)))
        assert row.revoked_at is not None


def test_same_token_presented_twice_within_grace_is_not_treated_as_theft():
    old = _issue()
    first = _rotate(old)
    second = _rotate(old)  # друга вкладка пред'явила той самий cookie майже одночасно

    assert second not in (old, first)
    # Обидва нащадки лишаються чинними: сім'ю не відкликано
    assert _rotate(first) != first
    assert _rotate(second) != second


def test_reuse_after_grace_revokes_the_whole_family():
    old = _issue()
    successor = _rotate(old)
    _age_revocation(old, REFRESH_REUSE_GRACE_SECONDS + 5)

    with session_factory()() as db, pytest.raises(ApiError) as caught:
        rotate_refresh_token(db, old)
    assert caught.value.code == "REFRESH_TOKEN_REUSED"

    # Відкликана вся сім'я, тож наступник більше не працює
    with session_factory()() as db, pytest.raises(ApiError):
        rotate_refresh_token(db, successor)


def test_token_cannot_be_used_after_logout_even_within_grace():
    old = _issue()
    current = _rotate(old)
    with session_factory()() as db:
        revoke_refresh_token(db, current)  # logout відкликає всю сім'ю

    with session_factory()() as db, pytest.raises(ApiError) as caught:
        rotate_refresh_token(db, old)
    assert caught.value.code == "REFRESH_TOKEN_REUSED"


def test_unknown_token_is_unauthorized():
    with session_factory()() as db, pytest.raises(ApiError) as caught:
        rotate_refresh_token(db, "no-such-token")
    assert caught.value.status_code == 401


def test_refresh_endpoint_accepts_the_same_cookie_twice_within_grace():
    old = _issue()
    client = TestClient(app)

    first = client.post("/api/v1/auth/refresh", headers={"Cookie": f"refresh_token={old}"})
    second = client.post("/api/v1/auth/refresh", headers={"Cookie": f"refresh_token={old}"})

    assert first.status_code == 200
    assert second.status_code == 200
