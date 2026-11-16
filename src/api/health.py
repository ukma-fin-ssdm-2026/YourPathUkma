"""
Перевірка готовності (readiness): GET /health/ready.

Перевіряє критичні залежності (БД, Microsoft Entra ID) паралельно, кожну з тайм-аутом.
Відповідь не розкриває внутрішніх деталей: причини збоїв лише в логах.
Збій залежності → 503 і статус "unhealthy" (швидка відмова: збій не маскується резервним значенням).

Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: pytest tests/reliability/test_health.py,
ruff check src/api tests/reliability, ручний запит GET /health/ready.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Callable, Optional

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from ..db.session import get_engine
from .microsoft import AUTHORITY
from .routes.system import API_VERSION
from .tokens import get_auth_settings

logger = logging.getLogger("yourpath.api")

router = APIRouter(tags=["System"])

CHECK_TIMEOUT_SECONDS = 2.0
NOT_CONFIGURED = "not_configured"

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="health")


def check_database() -> Optional[str]:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    return None


def check_microsoft() -> Optional[str]:
    settings = get_auth_settings()
    if not settings.tenant_id:
        return NOT_CONFIGURED  # вхід не налаштовано (локальна розробка): не вважаємо збоєм
    response = httpx.get(f"{AUTHORITY}/{settings.tenant_id}/discovery/v2.0/keys", timeout=CHECK_TIMEOUT_SECONDS)
    response.raise_for_status()
    return None


# Реєстр перевірок: тести підміняють елементи через monkeypatch.setitem (ін'єкція збою)
DEPENDENCIES: dict[str, Callable[[], Optional[str]]] = {
    "database": check_database,
    "microsoft": check_microsoft,
}


def _timed(check: Callable[[], Optional[str]]):
    started = time.perf_counter()
    result = check()
    return result, round((time.perf_counter() - started) * 1000)


@router.get(
    "/health/ready",
    summary="Перевірка готовності: критичні залежності (БД, Microsoft)",
    responses={
        200: {"description": "Усі критичні залежності доступні"},
        503: {"description": "Принаймні одна критична залежність недоступна"},
    },
)
def readiness_check():
    # Звичайний def: FastAPI виконає його в пулі потоків, синхронні БД і httpx не блокують event loop
    futures = {name: _executor.submit(_timed, check) for name, check in DEPENDENCIES.items()}
    deadline = time.monotonic() + CHECK_TIMEOUT_SECONDS

    checks: dict[str, dict] = {}
    healthy = True
    for name, future in futures.items():
        try:
            result, latency_ms = future.result(timeout=max(0.0, deadline - time.monotonic()))
            status = NOT_CONFIGURED if result == NOT_CONFIGURED else "up"
            checks[name] = {"status": status, "latency_ms": latency_ms}
        except FutureTimeout:
            future.cancel()
            logger.error("Перевірка здоров'я: %s не відповів за %.1f с", name, CHECK_TIMEOUT_SECONDS)
            checks[name] = {"status": "down", "latency_ms": None}
            healthy = False
        except Exception:
            # Межа перевірки: будь-який збій залежності = "down", причина лише в лозі
            logger.exception("Перевірка здоров'я: %s недоступний", name)
            checks[name] = {"status": "down", "latency_ms": None}
            healthy = False

    body = {"status": "healthy" if healthy else "unhealthy", "version": API_VERSION, "checks": checks}
    return JSONResponse(body, status_code=200 if healthy else 503)
