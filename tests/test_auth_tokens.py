"""
Тести абсолютного терміну життя refresh-сесій та очищення застарілих токенів (issue #218).

Використання ШІ: файл створено за допомогою Antigravity (Claude Sonnet 4.6, Google DeepMind) для issue #218.
Перевірено: pytest tests/test_auth_tokens.py.
"""

from datetime import timedelta

import pytest
from sqlalchemy import select

from src.api.auth_service import (
    create_refresh_token,
    hash_token,
    prune_refresh_tokens,
    rotate_refresh_token,
)
from src.api.common import ApiError
from src.db.base import utcnow
from src.db.models.users import RefreshToken, User
from src.db.session import session_factory


def test_refresh_token_rotation_succeeds_within_absolute_lifetime():
    with session_factory()() as db:
        user = db.scalar(select(User).limit(1))
        assert user is not None

        token_raw = create_refresh_token(db, user.id)
        db.commit()

        user_out, new_raw = rotate_refresh_token(db, token_raw)
        assert user_out.id == user.id
        assert new_raw != token_raw


def test_refresh_token_rotation_rejected_after_family_max_lifetime(monkeypatch):
    with session_factory()() as db:
        user = db.scalar(select(User).limit(1))
        token_raw = create_refresh_token(db, user.id)
        db.commit()

        future = utcnow() + timedelta(days=31)
        monkeypatch.setattr("src.api.auth_service.utcnow", lambda: future)

        with pytest.raises(ApiError) as exc_info:
            rotate_refresh_token(db, token_raw)

        assert exc_info.value.status_code == 401
        assert exc_info.value.code == "REFRESH_SESSION_EXPIRED"


def test_refresh_token_new_expiry_clamped_to_family_deadline(monkeypatch):
    with session_factory()() as db:
        user = db.scalar(select(User).limit(1))
        # Створюємо сім'ю на день 0
        token_raw = create_refresh_token(db, user.id)
        db.commit()

        # Емулюємо, що поточний токен діє до дня 32, а зараз день 28
        day_28 = utcnow() + timedelta(days=28)
        row = db.scalar(select(RefreshToken).where(RefreshToken.token_sha256 == hash_token(token_raw)))
        assert row is not None
        row.expires_at = day_28 + timedelta(days=4)
        db.commit()

        monkeypatch.setattr("src.api.auth_service.utcnow", lambda: day_28)

        _, new_raw = rotate_refresh_token(db, token_raw)
        new_row = db.scalar(select(RefreshToken).where(RefreshToken.token_sha256 == hash_token(new_raw)))
        assert new_row is not None
        # Термін дії має бути обмежений кінцем життя сім'ї (~2 дні від day_28, а не повні 7 днів)
        assert new_row.expires_at <= day_28 + timedelta(days=2, hours=1)


def test_prune_refresh_tokens_removes_expired_and_old_revoked():
    with session_factory()() as db:
        user = db.scalar(select(User).limit(1))
        now = utcnow()

        h_active = hash_token("val_active")
        h_expired = hash_token("val_expired")
        h_revoked = hash_token("val_revoked")

        t_active = RefreshToken(
            user_id=user.id,
            token_sha256=h_active,
            family_id="fam1",
            expires_at=now + timedelta(days=7),
        )
        t_expired = RefreshToken(
            user_id=user.id,
            token_sha256=h_expired,
            family_id="fam2",
            expires_at=now - timedelta(hours=2),
        )
        t_revoked = RefreshToken(
            user_id=user.id,
            token_sha256=h_revoked,
            family_id="fam3",
            expires_at=now + timedelta(days=1),
            revoked_at=now - timedelta(hours=2),
        )
        db.add_all([t_active, t_expired, t_revoked])
        db.commit()

        deleted = prune_refresh_tokens(db, now)
        assert deleted >= 2
        db.commit()

        assert db.scalar(select(RefreshToken).where(RefreshToken.token_sha256 == h_active)) is not None
        assert db.scalar(select(RefreshToken).where(RefreshToken.token_sha256 == h_expired)) is None
        assert db.scalar(select(RefreshToken).where(RefreshToken.token_sha256 == h_revoked)) is None
