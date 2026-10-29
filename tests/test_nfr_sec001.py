"""
Виконуваний NFR-тест SEC-001 (Лаб 2): доступ до збережених планів мають лише власники акаунта.

Поріг: 100 % спроб доступу до чужого плану завершуються відмовою (HTTP 403, код PLAN_FORBIDDEN).
Тест робить ATTEMPTS спроб від імені студента 42 до планів іншого студента, рахує частку відмов
і виводить виміряне значення.

Використання ШІ: файл створено за допомогою Claude. Перевірка: pytest і ruff локально.
"""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer test"}

FOREIGN_PLAN_IDS = [3]  # плани іншого студента із seed; студент 42 (авторизований у тестах) не є власником
ATTEMPTS = 100
THRESHOLD_PERCENT = 100.0


def test_sec001_foreign_plan_access_is_denied_in_all_attempts():
    """SEC-001: чужий план недоступний у 100 % спроб."""
    denied = 0
    for attempt in range(ATTEMPTS):
        plan_id = FOREIGN_PLAN_IDS[attempt % len(FOREIGN_PLAN_IDS)]
        response = client.get(f"/api/v1/plans/{plan_id}", headers=AUTH)
        if response.status_code == 403 and response.json().get("code") == "PLAN_FORBIDDEN":
            denied += 1

    measured = denied / ATTEMPTS * 100
    print(f"\nSEC-001: відмов {denied} з {ATTEMPTS} ({measured:.1f} %), поріг {THRESHOLD_PERCENT:.0f} %")
    assert measured >= THRESHOLD_PERCENT
