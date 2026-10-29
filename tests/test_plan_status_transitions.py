"""
Тестування переходів між станами плану (техніка тест-дизайну, бонус Лаб 7).

Таблиця «стан × подія» описана в docs/validation/test-plan.md, розділ «Бонуси». Один рядок таблиці дорівнює
одному параметру pytest, ID параметра (ST-01…ST-13) збігається з ID рядка таблиці.
Події: PUT /plans/{id}, DELETE /plans/{id}, POST /plans/{id}/submit. Редагувати, видаляти і подавати
можна лише план у статусі draft, в інших статусах сервер відповідає 409.

Використання ШІ: файл створено за допомогою Claude (Claude Code) за таблицею переходів. Перевірка: pytest,
у т. ч. що тест падає, якщо перевірку статусу в обробнику прибрати.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from src.api.main import app
from src.db import enums as db_enums
from src.db.models import IndividualPlan, PlanItem
from src.db.session import session_factory

client = TestClient(app)

FP = {"course_id": 101, "title": "Функціональне програмування", "trimester": 1, "credits": 5.0}
SECURITY = {"course_id": 102, "title": "Основи кібербезпеки", "trimester": 2, "credits": 4.0}
BODY = {"academic_year": 2027, "course": 3, "items": [FP, SECURITY]}

DRAFT = db_enums.PlanStatus.DRAFT
SUBMITTED = db_enums.PlanStatus.SUBMITTED
AWAITING_DEANERY = db_enums.PlanStatus.AWAITING_DEANERY
APPROVED = db_enums.PlanStatus.APPROVED

UNCHANGED = None  # стан плану після події не змінюється


@pytest.fixture
def make_plan(auth_headers):
    """Створює план студента 42 через API й виставляє потрібний статус у БД. Створені плани прибираються після тесту."""
    created = []

    def factory(status):
        response = client.post("/api/v1/plans", json={**BODY, "items": [FP]}, headers=auth_headers())
        assert (
            response.status_code == 201
        ), f"не вдалося створити план для тесту: {response.status_code} {response.text}"
        plan_id = response.json()["id"]
        created.append(plan_id)
        with session_factory()() as db:
            db.get(IndividualPlan, plan_id).status = status
            db.commit()
        return plan_id

    yield factory

    with session_factory()() as db:
        db.execute(delete(PlanItem).where(PlanItem.plan_id.in_(created)))
        db.execute(delete(IndividualPlan).where(IndividualPlan.id.in_(created)))
        db.commit()


def _stored_status(plan_id):
    with session_factory()() as db:
        return db.scalar(select(IndividualPlan.status).where(IndividualPlan.id == plan_id))


def _request(event, plan_id, headers):
    if event == "PUT":
        return client.put(f"/api/v1/plans/{plan_id}", json=BODY, headers=headers)
    if event == "DELETE":
        return client.delete(f"/api/v1/plans/{plan_id}", headers=headers)
    return client.post(f"/api/v1/plans/{plan_id}/submit", headers=headers)


NOT_ALLOWED = {"PUT": "PLAN_NOT_EDITABLE", "DELETE": "PLAN_NOT_DELETABLE", "SUBMIT": "PLAN_NOT_SUBMITTABLE"}


def _rejected(status, event, id_):
    return pytest.param(status, event, 409, NOT_ALLOWED[event], status, id=id_)


# (стан до, подія, очікуваний HTTP-статус, очікуваний код помилки, стан після)
TRANSITIONS = [
    pytest.param(DRAFT, "PUT", 200, None, DRAFT, id="ST-01"),
    pytest.param(DRAFT, "DELETE", 204, None, UNCHANGED, id="ST-02"),
    pytest.param(DRAFT, "SUBMIT", 200, None, SUBMITTED, id="ST-03"),
    _rejected(SUBMITTED, "PUT", "ST-04"),
    _rejected(SUBMITTED, "DELETE", "ST-05"),
    _rejected(SUBMITTED, "SUBMIT", "ST-06"),
    _rejected(AWAITING_DEANERY, "PUT", "ST-07"),
    _rejected(AWAITING_DEANERY, "DELETE", "ST-08"),
    _rejected(AWAITING_DEANERY, "SUBMIT", "ST-09"),
    _rejected(APPROVED, "PUT", "ST-10"),
    _rejected(APPROVED, "DELETE", "ST-11"),
    _rejected(APPROVED, "SUBMIT", "ST-12"),
]


@pytest.mark.parametrize("before, event, http_status, error_code, after", TRANSITIONS)
def test_plan_status_transition(make_plan, auth_headers, before, event, http_status, error_code, after):
    # Arrange
    plan_id = make_plan(before)

    # Act
    response = _request(event, plan_id, auth_headers())

    # Assert
    assert response.status_code == http_status
    if error_code:
        assert response.json()["code"] == error_code
    if after is UNCHANGED:
        assert _stored_status(plan_id) is None  # план видалено
    else:
        assert _stored_status(plan_id) == after


def test_submit_with_rule_violation_keeps_draft(make_plan, auth_headers):
    """ST-13: подання draft-плану, що порушує правила, → 422 PLAN_VALIDATION_FAILED, статус лишається draft."""
    # Arrange: єдиний елемент плану позначаємо вільним вибором: «план лише з вільних» порушує правила
    # незалежно від того, чи дисципліна 101 у seed-даних має напрямки
    plan_id = make_plan(DRAFT)
    with session_factory()() as db:
        item = db.scalar(select(PlanItem).where(PlanItem.plan_id == plan_id))
        item.category = db_enums.PlanItemCategory.FREE_CHOICE
        db.commit()

    # Act
    response = client.post(f"/api/v1/plans/{plan_id}/submit", headers=auth_headers())

    # Assert
    assert response.status_code == 422
    assert response.json()["code"] == "PLAN_VALIDATION_FAILED"
    assert "ONLY_FREE_ELECTIVES" in response.text
    assert _stored_status(plan_id) == DRAFT
