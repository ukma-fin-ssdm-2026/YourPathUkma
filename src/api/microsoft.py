import hmac
import logging
from dataclasses import dataclass
from functools import lru_cache

import httpx
import jwt
from jwt import PyJWKClient

from .common import ApiError
from .tokens import AuthSettings, get_auth_settings

logger = logging.getLogger("yourpath.api")

AUTHORITY = "https://login.microsoftonline.com"
LOGIN_FAILED_MESSAGE = "Не вдалося підтвердити вхід через Microsoft"


@dataclass(frozen=True)
class MicrosoftIdentity:
    oid: str
    tid: str
    email: str
    full_name: str


@lru_cache(maxsize=None)
def _jwks_client(tenant_id: str) -> PyJWKClient:
    return PyJWKClient(f"{AUTHORITY}/{tenant_id}/discovery/v2.0/keys", cache_keys=True, lifespan=3600, timeout=10)


def _configured_settings() -> AuthSettings:
    settings = get_auth_settings()
    if not settings.tenant_id or not settings.client_id:
        raise ApiError(503, "AUTH_NOT_CONFIGURED", "Вхід через Microsoft не налаштовано")
    return settings


def _login_failed(code: str = "INVALID_AUTH_CODE") -> ApiError:
    return ApiError(401, code, LOGIN_FAILED_MESSAGE)


def _exchange_code(code: str, code_verifier: str, redirect_uri: str) -> str:
    settings = _configured_settings()
    data = {
        "client_id": settings.client_id,
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
        "scope": "openid profile email",
    }
    if settings.client_secret:
        data["client_secret"] = settings.client_secret
    try:
        response = httpx.post(f"{AUTHORITY}/{settings.tenant_id}/oauth2/v2.0/token", data=data, timeout=10.0)
    except httpx.HTTPError:
        logger.exception("Microsoft token endpoint недоступний")
        raise ApiError(503, "AUTH_PROVIDER_UNAVAILABLE", "Microsoft тимчасово недоступний")
    if response.status_code != 200:
        try:
            body = response.json()
        except ValueError:
            body = {}
        logger.warning(
            "Microsoft відхилив код: %s %s %s",
            response.status_code,
            body.get("error"),
            str(body.get("error_description", ""))[:300],
        )
        raise _login_failed()
    try:
        id_token = response.json().get("id_token")
    except ValueError:
        id_token = None
    if not id_token:
        raise _login_failed()
    return id_token


def _verify_id_token(id_token: str, nonce: str) -> dict:
    settings = get_auth_settings()
    try:
        signing_key = _jwks_client(settings.tenant_id).get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.client_id,
            issuer=f"{AUTHORITY}/{settings.tenant_id}/v2.0",
            leeway=30,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError:
        logger.warning("Некоректний id_token від Microsoft", exc_info=True)
        raise _login_failed("INVALID_ID_TOKEN")
    if claims.get("tid") != settings.tenant_id:
        raise _login_failed("INVALID_ID_TOKEN")
    if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise _login_failed("INVALID_NONCE")
    return claims


def authenticate(code: str, code_verifier: str, redirect_uri: str, nonce: str) -> MicrosoftIdentity:
    claims = _verify_id_token(_exchange_code(code, code_verifier, redirect_uri), nonce)
    settings = get_auth_settings()
    email = str(claims.get("email") or claims.get("preferred_username") or "").strip().lower()
    if "@" not in email or email.rpartition("@")[2] not in settings.allowed_email_domains:
        raise ApiError(403, "EMAIL_DOMAIN_NOT_ALLOWED", "Вхід дозволено лише з корпоративною поштою НаУКМА")
    oid = claims.get("oid")
    if not oid:
        raise _login_failed("INVALID_ID_TOKEN")
    full_name = str(claims.get("name") or email.split("@")[0])[:200]
    return MicrosoftIdentity(oid=str(oid), tid=str(claims["tid"]), email=email, full_name=full_name)
