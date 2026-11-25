"""
Тести серверного обмеження частоти запитів (Rate Limiting, Контракт §1.6, issue #298).

Перевіряють:
- межі N / N+1 (100/хв глобально, 5/10 хв завантаження деканату, 20/добу AI);
- закінчення ковзного вікна (window expiration);
- ізоляцію користувачів (JWT user_id) та неавтентифікованих клієнтів (IP без довіри до довільного X-Forwarded-For);
- повернення 429 RATE_LIMITED із заголовком Retry-After та узгодженим request_id;
- відхилення 6-го завантаження документа деканату без обробки файлу;
- конкурентну потокобезпеку при паралельних запитах.

Використання ШІ: файл створено за допомогою Antigravity (Gemini 4 Hydrogen) для перевірки реалізації #298.
Перевірка: pytest tests/test_rate_limiting.py.
"""

from __future__ import annotations

import threading
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import delete

from src.api.common import get_current_student_id
from src.api.main import app
from src.api.rate_limiter import (
    SlidingWindowRateLimiter,
    deanery_upload_limiter,
    get_client_ip,
)
from src.db import enums as db_enums
from src.db.base import utcnow
from src.db.models.ai import PlanGeneration
from src.db.models.deanery import DeaneryPlanDocument
from src.db.session import session_factory

client = TestClient(app)


def test_sliding_window_boundary_and_expiration():
    current_time = [1000.0]
    limiter = SlidingWindowRateLimiter(
        max_requests=3,
        window_seconds=60.0,
        time_func=lambda: current_time[0],
    )

    for _ in range(3):
        res = limiter.check("usr:1")
        assert res.allowed is True

    # N+1 запит має бути відхилений
    blocked = limiter.check("usr:1")
    assert blocked.allowed is False
    assert blocked.retry_after == 60
    assert blocked.remaining == 0

    # Через 30 секунд все ще заблоковано, Retry-After зменшився
    current_time[0] += 30.0
    blocked_later = limiter.check("usr:1")
    assert blocked_later.allowed is False
    assert blocked_later.retry_after == 30

    # Після закінчення вікна (60 секунд) запит знову дозволено
    current_time[0] += 30.01
    allowed_again = limiter.check("usr:1")
    assert allowed_again.allowed is True


def test_global_rate_limit_n_and_n_plus_1(auth_headers):
    headers = auth_headers(user_id=42)
    for i in range(100):
        resp = client.get("/api/v1/health/ping", headers=headers)
        # /api/v1/health/ping може повертати 404 (немає такого маршруту), але головне — не 429
        assert resp.status_code != 429, f"Запит #{i + 1} несподівано обмежено"

    # 101-й запит у тому ж вікні має повернути 429 RATE_LIMITED + Retry-After + request_id
    blocked = client.get("/api/v1/health/ping", headers=headers)
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    retry_after = int(blocked.headers["Retry-After"])
    assert 1 <= retry_after <= 60

    body = blocked.json()
    assert body["code"] == "RATE_LIMITED"
    assert body["request_id"]
    assert blocked.headers.get("X-Request-ID") == body["request_id"]


def test_global_rate_limit_user_isolation(auth_headers):
    headers_a = auth_headers(user_id=1001)
    headers_b = auth_headers(user_id=1002)

    # Користувач A вичерпує свій ліміт
    for _ in range(100):
        resp = client.get("/api/v1/directions", headers=headers_a)
        assert resp.status_code == 200

    blocked_a = client.get("/api/v1/directions", headers=headers_a)
    assert blocked_a.status_code == 429

    # Користувач B не заблокований
    resp_b = client.get("/api/v1/directions", headers=headers_b)
    assert resp_b.status_code == 200

    # Неавтентифікований клієнт (за IP) також ізольований від користувача A
    resp_anon = client.get("/api/v1/directions")
    assert resp_anon.status_code != 429


def test_unauthenticated_ip_does_not_trust_arbitrary_xff(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
    fake_req = SimpleNamespace(
        client=SimpleNamespace(host="198.51.100.10"),
        headers={"X-Forwarded-For": "203.0.113.99"},
    )
    assert get_client_ip(fake_req) == "198.51.100.10"


def test_trusted_proxy_uses_xff(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.0/8, 127.0.0.1")
    fake_req = SimpleNamespace(
        client=SimpleNamespace(host="10.0.1.5"),
        headers={"X-Forwarded-For": "203.0.113.50, 10.0.1.5"},
    )
    assert get_client_ip(fake_req) == "203.0.113.50"


def test_system_and_options_requests_exempt_from_rate_limit(auth_headers):
    headers = auth_headers(user_id=42)
    for _ in range(100):
        client.get("/api/v1/directions", headers=headers)

    assert client.get("/api/v1/directions", headers=headers).status_code == 429

    # Системні маршрути та CORS preflight не блокуються
    assert client.get("/health").status_code == 200
    assert client.options("/api/v1/directions", headers=headers).status_code != 429


def test_deanery_upload_rate_limit_rejects_sixth_without_reading_file(auth_headers):
    headers = auth_headers(user_id=42)
    files = {"file": ("test.pdf", b"%PDF-1.4 fake content", "application/pdf")}
    data = {"academic_year": 2026}

    for i in range(5):
        resp = client.post("/api/v1/deanery-documents", files=files, data=data, headers=headers)
        assert resp.status_code == 202, f"Завантаження #{i + 1} мало бути прийняте"

    # 6-те завантаження має бути відхилене з 429 без обробки/збереження файлу
    with patch("fastapi.UploadFile.read") as mock_read:
        sixth = client.post("/api/v1/deanery-documents", files=files, data=data, headers=headers)
        assert sixth.status_code == 429
        assert "Retry-After" in sixth.headers
        assert int(sixth.headers["Retry-After"]) >= 1
        assert sixth.json()["code"] == "RATE_LIMITED"
        assert sixth.json()["request_id"]
        mock_read.assert_not_called()

    # Очистимо створені тестові документи
    with session_factory()() as db:
        db.execute(delete(DeaneryPlanDocument).where(DeaneryPlanDocument.student_id == 42))
        db.commit()


def test_deanery_upload_window_expiration(monkeypatch, auth_headers):
    now = [2000.0]
    monkeypatch.setattr(deanery_upload_limiter, "time_func", lambda: now[0])
    headers = auth_headers(user_id=42)
    files = {"file": ("test.pdf", b"%PDF-1.4 fake content", "application/pdf")}
    data = {"academic_year": 2026}

    for _ in range(5):
        assert client.post("/api/v1/deanery-documents", files=files, data=data, headers=headers).status_code == 202

    assert client.post("/api/v1/deanery-documents", files=files, data=data, headers=headers).status_code == 429

    # Через 10 хвилин + 1 секунду вікно спливає
    now[0] += 601.0
    resp = client.post("/api/v1/deanery-documents", files=files, data=data, headers=headers)
    assert resp.status_code == 202

    with session_factory()() as db:
        db.execute(delete(DeaneryPlanDocument).where(DeaneryPlanDocument.student_id == 42))
        db.commit()


def test_ai_generation_daily_limit_returns_retry_after(auth_headers):
    headers = auth_headers(user_id=42)
    now = utcnow()
    with session_factory()() as db:
        db.execute(delete(PlanGeneration).where(PlanGeneration.student_id == 42))
        for i in range(20):
            db.add(
                PlanGeneration(
                    student_id=42,
                    academic_year=2026,
                    status=db_enums.GenerationStatus.SUCCEEDED,
                    created_at=now - timedelta(hours=23) + timedelta(minutes=i),
                )
            )
        db.commit()

    try:
        app.dependency_overrides[get_current_student_id] = lambda: 42
        resp = client.post(
            "/api/v1/plan-generations",
            json={"academic_year": 2026, "direction_ids": [1]},
            headers=headers,
        )
        assert resp.status_code == 429
        assert resp.json()["code"] == "RATE_LIMITED"
        assert "Retry-After" in resp.headers
        retry_after = int(resp.headers["Retry-After"])
        # Найстаріша генерація була 23 години тому, тож чекати близько 1 години (~3600 с)
        assert 1 <= retry_after <= 3600
    finally:
        with session_factory()() as db:
            db.execute(delete(PlanGeneration).where(PlanGeneration.student_id == 42))
            db.commit()


def test_concurrent_rate_limiter_preserves_exact_limit_and_allowed_rate():
    # 1) Перевірка на перевищення при паралельних запитах: 10 потоків по 15 запитів при ліміті 100
    limiter = SlidingWindowRateLimiter(max_requests=100, window_seconds=60.0)
    results = []
    lock = threading.Lock()
    barrier = threading.Barrier(10)

    def worker(count: int):
        barrier.wait()
        local_res = [limiter.check("usr:concurrent") for _ in range(count)]
        with lock:
            results.extend(local_res)

    threads = [threading.Thread(target=worker, args=(15,)) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    allowed_count = sum(1 for r in results if r.allowed)
    blocked_count = sum(1 for r in results if not r.allowed)
    assert allowed_count == 100
    assert blocked_count == 50
    assert all(r.retry_after >= 1 for r in results if not r.allowed)

    # 2) Збереження дозволеної частоти при паралельних запитах: 10 потоків по 10 запитів при ліміті 100
    limiter.reset()
    results_ok = []
    barrier2 = threading.Barrier(10)

    def worker_ok():
        barrier2.wait()
        local_res = [limiter.check("usr:concurrent_ok") for _ in range(10)]
        with lock:
            results_ok.extend(local_res)

    threads2 = [threading.Thread(target=worker_ok) for _ in range(10)]
    for t in threads2:
        t.start()
    for t in threads2:
        t.join()

    assert len(results_ok) == 100
    assert all(r.allowed for r in results_ok)
