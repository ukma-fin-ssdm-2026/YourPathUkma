"""
Тести надійності: обробка помилок (Лаб 9, знахідка №8 та спільний обробник винятків).

Система не падає на несподіваному винятку, не розкриває внутрішніх деталей і не ковтає збій мовчки.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: запуск `pytest tests/reliability`
(тести спершу падали на коді до виправлень, потім пройшли).
"""

import logging

from fastapi.testclient import TestClient

from src.api.main import app
from src.api.tokens import decode_access_token

INTERNAL_DETAIL = "internal-db-host:5432 connection refused"


def _broken_db():
    raise RuntimeError(INTERNAL_DETAIL)
    yield  # pragma: no cover  (робить функцію генератором, як справжній get_db)


def test_unexpected_exception_returns_generic_500_without_internal_details():
    from src.db.session import get_db

    app.dependency_overrides[get_db] = _broken_db
    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/deanery-documents", headers={"Authorization": "Bearer test"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "INTERNAL_ERROR"
    assert INTERNAL_DETAIL not in response.text
    assert "RuntimeError" not in response.text


def test_garbage_token_is_rejected_and_logged(caplog):
    garbage = "not.a.jwt"
    with caplog.at_level(logging.INFO, logger="src.api.tokens"):
        assert decode_access_token(garbage) is None

    assert any("Токен доступу відхилено" in r.getMessage() for r in caplog.records)
    assert garbage not in caplog.text  # токен не має потрапляти в лог
