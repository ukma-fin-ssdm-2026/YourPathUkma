import hashlib
import secrets
import uuid
from datetime import timedelta
from typing import Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import enums as db_enums
from ..db.base import utcnow
from ..db.models.users import RefreshToken, StudentProfile, User
from .common import ApiError
from .microsoft import MicrosoftIdentity
from .tokens import REFRESH_TOKEN_TTL_SECONDS, get_auth_settings


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


def create_refresh_token(db: Session, user_id: int, family_id: Optional[str] = None) -> str:
    raw = secrets.token_urlsafe(48)
    db.add(
        RefreshToken(
            user_id=user_id,
            token_sha256=hash_token(raw),
            family_id=family_id or uuid.uuid4().hex,
            expires_at=utcnow() + timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS),
        )
    )
    return raw


def _revoke_family(db: Session, family_id: str) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def rotate_refresh_token(db: Session, raw: str) -> Tuple[User, str]:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_sha256 == hash_token(raw)).with_for_update())
    if row is None:
        raise _unauthorized()
    now = utcnow()
    if row.revoked_at is not None:
        _revoke_family(db, row.family_id)
        db.commit()
        raise _unauthorized("REFRESH_TOKEN_REUSED")
    if row.expires_at <= now:
        raise _unauthorized("REFRESH_TOKEN_EXPIRED")
    user = db.get(User, row.user_id)
    if user is None:
        raise _unauthorized()
    row.revoked_at = now
    new_raw = create_refresh_token(db, user.id, row.family_id)
    db.commit()
    return user, new_raw


def revoke_refresh_token(db: Session, raw: str) -> None:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_sha256 == hash_token(raw)))
    if row is not None:
        _revoke_family(db, row.family_id)
        db.commit()
