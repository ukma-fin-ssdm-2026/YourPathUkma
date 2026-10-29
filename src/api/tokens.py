import os
import time
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional
import jwt

ACCESS_TOKEN_TTL_SECONDS = 900
REFRESH_TOKEN_TTL_SECONDS = 7 * 24 * 3600
JWT_ISSUER = "yourpathukma-api"
JWT_AUDIENCE = "yourpathukma-web"
MIN_SECRET_LENGTH = 32


@dataclass(frozen=True)
class AuthSettings:
    tenant_id: str
    client_id: str
    client_secret: str
    jwt_secret: str
    allowed_email_domains: frozenset
    admin_emails: frozenset
    cookie_secure: bool
    cookie_samesite: str


def _csv(name: str, default: str = "") -> frozenset:
    return frozenset(v.strip().lower() for v in os.getenv(name, default).split(",") if v.strip())


@lru_cache(maxsize=None)
def get_auth_settings() -> AuthSettings:
    return AuthSettings(
        tenant_id=os.getenv("MS_TENANT_ID", "").strip(),
        client_id=os.getenv("MS_CLIENT_ID", "").strip(),
        client_secret=os.getenv("MS_CLIENT_SECRET", "").strip(),
        jwt_secret=os.getenv("JWT_SECRET", ""),
        allowed_email_domains=_csv("ALLOWED_EMAIL_DOMAINS", "ukma.edu.ua"),
        admin_emails=_csv("ADMIN_EMAILS"),
        cookie_secure=os.getenv("COOKIE_SECURE", "1") != "0",
        cookie_samesite=os.getenv("COOKIE_SAMESITE", "strict").strip().lower(),
    )


def validate_auth_settings(production: bool) -> None:
    settings = get_auth_settings()
    if len(settings.jwt_secret) < MIN_SECRET_LENGTH:
        raise RuntimeError(f"JWT_SECRET має містити щонайменше {MIN_SECRET_LENGTH} символів")
    if settings.cookie_samesite not in {"strict", "lax", "none"}:
        raise RuntimeError("COOKIE_SAMESITE має бути strict, lax або none")
    if settings.cookie_samesite == "none" and not settings.cookie_secure:
        raise RuntimeError("COOKIE_SAMESITE=none потребує COOKIE_SECURE=1")
    if production and not (settings.tenant_id and settings.client_id):
        raise RuntimeError("У продакшні потрібні MS_TENANT_ID і MS_CLIENT_ID")
    if production and not settings.cookie_secure:
        raise RuntimeError("COOKIE_SECURE=0 заборонено при APP_ENV=production")


def issue_access_token(user_id: int, role: str) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + ACCESS_TOKEN_TTL_SECONDS,
        "jti": uuid.uuid4().hex,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    return jwt.encode(payload, get_auth_settings().jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> Optional[int]:
    try:
        claims = jwt.decode(
            token,
            get_auth_settings().jwt_secret,
            algorithms=["HS256"],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={"require": ["exp", "iat", "sub"]},
        )
        return int(claims["sub"])
    except (jwt.PyJWTError, ValueError):
        return None
