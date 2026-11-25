"""
Сервіс автентифікації: обробка Microsoft identity, створення та ротація refresh-токенів.

Використання ШІ: файл доповнено за допомогою Antigravity (Claude Sonnet 4.6, Google DeepMind):
додано абсолютний термін життя сесії сім'ї токенів (30 діб) та періодичне очищення таблиці токенів (issue #218).
Перевірено: pytest tests/test_auth.py tests/test_auth_tokens.py.
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import enums as db_enums
from ..db.base import utcnow
from ..db.models.users import RefreshToken, StudentProfile, User
from .common import ApiError
from .microsoft import MicrosoftIdentity
from .tokens import REFRESH_TOKEN_TTL_SECONDS, get_auth_settings

# Скільки секунд після ротації старий refresh-токен ще вважається «щойно ротованим», а не вкраденим:
# друга вкладка або повтор після втраченої відповіді пред'являють той самий cookie майже одночасно.
REFRESH_REUSE_GRACE_SECONDS = 10

# Абсолютний ліміт життя сім'ї refresh-токенів (за замовчуванням 30 діб, issue #218)
REFRESH_FAMILY_MAX_LIFETIME_SECONDS = int(os.getenv("REFRESH_FAMILY_MAX_LIFETIME_SECONDS", 30 * 86400))


def _unauthorized(code: str = "UNAUTHORIZED") -> ApiError:
    return ApiError(401, code, "Відсутній або некоректний токен авторизації")


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _find_user(db: Session, identity: MicrosoftIdentity) -> Optional[User]:
    user = db.scalar(select(User).where(User.ms_oid == identity.oid))
    if user is None:
        user = db.scalar(select(User).where(User.email == identity.email, User.ms_tid.is_(None)))
    return user


def sign_in_user(db: Session, identity: MicrosoftIdentity) -> User:
    settings = get_auth_settings()
    for _ in range(2):
        user = _find_user(db, identity)
        if user is None:
            user = User(
                ms_oid=identity.oid,
                ms_tid=identity.tid,
                email=identity.email,
                full_name=identity.full_name,
                role=db_enums.UserRole.STUDENT,
                student_profile=StudentProfile(),
            )
            db.add(user)
        else:
            user.ms_oid = identity.oid
            user.ms_tid = identity.tid
            user.full_name = identity.full_name
        if identity.email in settings.admin_emails:
            user.role = db_enums.UserRole.ADMIN
        user.last_login_at = utcnow()
        try:
            db.flush()
            return user
        except IntegrityError:
            db.rollback()
    raise ApiError(409, "LOGIN_CONFLICT", "Не вдалося завершити вхід, спробуйте ще раз")


def _family_created_at(db: Session, row: RefreshToken) -> datetime:
    family_id = row.family_id
    if len(family_id) == 32:
        try:
            ts = int(family_id[:8], 16)
            if 1700000000 <= ts <= 4100000000:
                return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OverflowError):
            pass
    earliest = db.scalar(select(func.min(RefreshToken.created_at)).where(RefreshToken.family_id == family_id))
    return earliest or row.created_at


def prune_refresh_tokens(db: Session, now: Optional[datetime] = None) -> int:
    """
    Видалення прострочених і застарілих відкликаних токенів (issue #218).
    Видаляє:
    - токени, термін яких сплив понад 1 годину тому;
    - відкликані токени, старші за grace-вікно (понад 1 годину тому).
    """
    if now is None:
        now = utcnow()
    cutoff = now - timedelta(hours=1)
    stmt = delete(RefreshToken).where(
        (RefreshToken.expires_at < cutoff) | (RefreshToken.revoked_at.is_not(None) & (RefreshToken.revoked_at < cutoff))
    )
    result = db.execute(stmt)
    return result.rowcount


def create_refresh_token(
    db: Session,
    user_id: int,
    family_id: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> str:
    now = utcnow()
    if family_id is None:
        family_id = f"{int(now.timestamp()):08x}{secrets.token_hex(12)}"
    if expires_at is None:
        expires_at = now + timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS)
    raw = secrets.token_urlsafe(48)
    db.add(
        RefreshToken(
            user_id=user_id,
            token_sha256=hash_token(raw),
            family_id=family_id,
            expires_at=expires_at,
        )
    )
    return raw


def _revoke_family(db: Session, family_id: str) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def _rotated_just_now(db: Session, row: RefreshToken, now) -> bool:
    """
    Токен відкликано через ротацію щойно (в межах grace-вікна), і в «сім'ї» ще є чинний наступник.
    Після виходу (logout) відкликається вся «сім'я», чинного наступника немає, тож таке не проходить.
    """
    if now - row.revoked_at > timedelta(seconds=REFRESH_REUSE_GRACE_SECONDS):
        return False
    successor = db.scalar(
        select(RefreshToken.id)
        .where(
            RefreshToken.family_id == row.family_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
        .limit(1)
    )
    return successor is not None


def rotate_refresh_token(db: Session, raw: str) -> Tuple[User, str]:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_sha256 == hash_token(raw)).with_for_update())
    if row is None:
        raise _unauthorized()
    now = utcnow()
    if row.revoked_at is not None and not _rotated_just_now(db, row, now):
        _revoke_family(db, row.family_id)
        db.commit()
        raise _unauthorized("REFRESH_TOKEN_REUSED")

    # Перевірка абсолютного терміну життя сім'ї токенів (issue #218)
    family_start = _family_created_at(db, row)
    if now - family_start >= timedelta(seconds=REFRESH_FAMILY_MAX_LIFETIME_SECONDS):
        _revoke_family(db, row.family_id)
        db.commit()
        raise _unauthorized("REFRESH_SESSION_EXPIRED")

    if row.expires_at <= now:
        raise _unauthorized("REFRESH_TOKEN_EXPIRED")

    user = db.get(User, row.user_id)
    if user is None:
        raise _unauthorized()
    if row.revoked_at is None:
        row.revoked_at = now

    family_deadline = family_start + timedelta(seconds=REFRESH_FAMILY_MAX_LIFETIME_SECONDS)
    normal_expiry = now + timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS)
    new_expires_at = min(normal_expiry, family_deadline)

    new_raw = create_refresh_token(db, user.id, row.family_id, expires_at=new_expires_at)
    prune_refresh_tokens(db, now)
    db.commit()
    return user, new_raw


def revoke_refresh_token(db: Session, raw: str) -> None:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_sha256 == hash_token(raw)))
    if row is not None:
        _revoke_family(db, row.family_id)
        db.commit()
