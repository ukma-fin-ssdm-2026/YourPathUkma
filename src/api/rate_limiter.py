"""
Серверний механізм обмеження частоти запитів (Rate Limiting) за Контрактом §1.6 (issue #298).

Підтримує:
- 100 запитів/хвилину на автентифікованого користувача (або на IP для неавтентифікованих);
- 5 завантажень документів деканату за 10 хвилин на користувача;
- атомарне вікно, повернення заголовка Retry-After;
- налаштовувану підтримку довірених проксі (TRUSTED_PROXIES) для коректного визначення client IP;
- ізоляцію користувачів та потокобезпеку.

Використання ШІ: модуль реалізовано за допомогою Antigravity (Gemini 2.5 Pro) за вимогами #298 та Контракту §1.6.
Перевірка: pytest, ruff.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, List, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .common import (
    REQUEST_ID_HEADER,
    ErrorResponse,
    get_request_id,
)
from .tokens import decode_access_token

logger = logging.getLogger("yourpath.api.rate_limiter")

DEFAULT_GLOBAL_LIMIT = 100
DEFAULT_GLOBAL_WINDOW = 60.0

DEFAULT_DEANERY_UPLOAD_LIMIT = 5
DEFAULT_DEANERY_UPLOAD_WINDOW = 600.0


def _parse_trusted_proxies() -> List[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    raw = os.getenv("TRUSTED_PROXIES", "").strip()
    if not raw:
        return []
    networks = []
    for item in raw.split(","):
        part = item.strip()
        if not part:
            continue
        try:
            if "/" in part:
                networks.append(ipaddress.ip_network(part, strict=False))
            else:
                ip = ipaddress.ip_address(part)
                networks.append(ipaddress.ip_network(f"{ip}/{ip.max_prefixlen}"))
        except ValueError:
            logger.warning("Некоректний запис у TRUSTED_PROXIES: %s", part)
    return networks


def get_client_ip(request: Request) -> str:
    """
    Визначає безпечну клієнтську IP-адресу.
    Якщо прямий клієнт належить до TRUSTED_PROXIES, враховується ланцюжок X-Forwarded-For.
    Інакше повертається прямий IP з request.client.host без довіри до клієнтських заголовків.
    """
    peer_host = request.client.host if request.client else "127.0.0.1"
    try:
        peer_ip = ipaddress.ip_address(peer_host)
    except ValueError:
        return peer_host

    trusted = _parse_trusted_proxies()
    is_peer_trusted = any(peer_ip in net for net in trusted)

    if not is_peer_trusted:
        return str(peer_ip)

    xff = request.headers.get("X-Forwarded-For")
    if not xff:
        return str(peer_ip)

    ips = [p.strip() for p in xff.split(",") if p.strip()]
    for candidate in reversed(ips):
        try:
            c_ip = ipaddress.ip_address(candidate)
            if not any(c_ip in net for net in trusted):
                return str(c_ip)
        except ValueError:
            continue

    return str(peer_ip)


def extract_user_identifier(request: Request) -> str:
    """
    Витягує ідентифікатор користувача для обмеження запитів.
    1. Якщо запит має валідний Bearer токен -> 'usr:<user_id>'
    2. Інакше -> 'ip:<client_ip>'
    """
    auth_header = request.headers.get("Authorization", "").strip()
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token:
            user_id = decode_access_token(token)
            if user_id is not None:
                return f"usr:{user_id}"
    return f"ip:{get_client_ip(request)}"


@dataclass
class RateLimitResult:
    allowed: bool
    retry_after: int = 0
    remaining: int = 0
    limit: int = 0


class SlidingWindowRateLimiter:
    """
    Потокобезпечний обмежувач частоти запитів за алгоритмом ковзного вікна (sliding window).
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        time_func: Optional[Callable[[], float]] = None,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.time_func = time_func or time.time
        self._history: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, now: Optional[float] = None) -> RateLimitResult:
        if now is None:
            now = self.time_func()
        window_start = now - self.window_seconds

        with self._lock:
            timestamps = self._history.get(key)
            if timestamps is None:
                timestamps = deque()
                self._history[key] = timestamps

            while timestamps and timestamps[0] <= window_start:
                timestamps.popleft()

            if len(timestamps) >= self.max_requests:
                oldest = timestamps[0]
                retry_after = max(1, int(oldest + self.window_seconds - now + 0.999))
                return RateLimitResult(
                    allowed=False,
                    retry_after=retry_after,
                    remaining=0,
                    limit=self.max_requests,
                )

            timestamps.append(now)
            remaining = max(0, self.max_requests - len(timestamps))
            return RateLimitResult(
                allowed=True,
                retry_after=0,
                remaining=remaining,
                limit=self.max_requests,
            )

    def reset(self) -> None:
        with self._lock:
            self._history.clear()


# Глобальні екземпляри лімітерів
global_rate_limiter = SlidingWindowRateLimiter(
    max_requests=int(os.getenv("RATE_LIMIT_GLOBAL_MAX", str(DEFAULT_GLOBAL_LIMIT))),
    window_seconds=float(os.getenv("RATE_LIMIT_GLOBAL_WINDOW", str(DEFAULT_GLOBAL_WINDOW))),
)

deanery_upload_limiter = SlidingWindowRateLimiter(
    max_requests=int(os.getenv("RATE_LIMIT_DEANERY_MAX", str(DEFAULT_DEANERY_UPLOAD_LIMIT))),
    window_seconds=float(os.getenv("RATE_LIMIT_DEANERY_WINDOW", str(DEFAULT_DEANERY_UPLOAD_WINDOW))),
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware загального обмеження частоти запитів (100 / хв на користувача або IP).
    Пропускає системні маршрути (/health, /api-docs, /redoc, /openapi.json тощо) та CORS preflight.
    """

    def __init__(
        self,
        app,
        limiter: Optional[SlidingWindowRateLimiter] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        super().__init__(app)
        self.limiter = limiter or global_rate_limiter
        self.enabled = enabled if enabled is not None else os.getenv("ENABLE_RATE_LIMITER", "1") != "0"

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        # CORS preflight запити не обмежуємо
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        # Пропускаємо системні та службові маршрути
        if path in ("/health", "/health/ready", "/health/live") or path.startswith(
            ("/api-docs", "/redoc", "/openapi.")
        ):
            return await call_next(request)

        # Перевірка лише для запитів до API (/api/v1/...)
        if not path.startswith("/api/v1"):
            return await call_next(request)

        user_key = extract_user_identifier(request)
        result = self.limiter.check(user_key)

        if not result.allowed:
            request_id = get_request_id(request)
            error_body = ErrorResponse(
                code="RATE_LIMITED",
                message="Забагато запитів, спробуйте пізніше",
                details=[],
                request_id=request_id,
            )
            headers = {
                REQUEST_ID_HEADER: request_id,
                "Retry-After": str(result.retry_after),
            }
            return JSONResponse(
                status_code=429,
                content=error_body.model_dump(mode="json"),
                headers=headers,
            )

        response = await call_next(request)
        return response
