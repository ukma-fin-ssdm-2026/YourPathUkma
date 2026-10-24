"""Тести: напрямки розвитку та прив'язка до дисциплін (contract.md §3.9).
Використання ШІ: тести написано за допомогою Claude.
Перевірка: pytest локально та в CI.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.api.common import MOCK_STUDENT_ID
from src.api.main import app
from src.db import enums as db_enums
from src.db.models.catalog import Course
from src.db.models.users import User
from src.db.session import session_factory

client = TestClient(app)
AUTH = {"Authorization": "Bearer test"}
DIRECTIONS_URL = "/api/v1/admin/directions"


@pytest.fixture
def admin():
    """Тимчасово робить тестового користувача адміністратором; після тесту повертає стару роль."""
    with session_factory()() as db:
        user = db.get(User, MOCK_STUDENT_ID)
        original_role = user.role
        user.role = db_enums.UserRole.ADMIN
        db.commit()
    yield
    with session_factory()() as db:
        user = db.get(User, MOCK_STUDENT_ID)
        user.role = original_role
        db.commit()


def _unique_name() -> str:
    return f"Dir-{uuid.uuid4().hex[:8]}"


def _create(name=None, description=None):
    payload = {"name": name or _unique_name()}
    if description is not None:
        payload["description"] = description
    return client.post(DIRECTIONS_URL, json=payload, headers=AUTH)


def _delete(direction_id):
    return client.delete(f"{DIRECTIONS_URL}/{direction_id}", headers=AUTH)


@pytest.fixture
def direction(admin):
    response = _create(description="тестовий опис")
    assert response.status_code == 201
    data = response.json()
    yield data
    _delete(data["id"])


def _first_course():
    with session_factory()() as db:
        course = db.scalars(select(Course)).first()
        return course.id, sorted(d.id for d in course.directions)


def _set_directions(course_id, direction_ids):
    return client.put(
        f"/api/v1/admin/disciplines/{course_id}/directions",
        json={"direction_ids": direction_ids},
        headers=AUTH,
    )


# --- Створення ---


def test_create_direction_strips_name(admin):
    suffix = uuid.uuid4().hex[:8]

    response = _create(name=f"  Pad-{suffix}  ")

    assert response.status_code == 201
    assert response.json()["name"] == f"Pad-{suffix}"
    _delete(response.json()["id"])


def test_create_direction_rejects_duplicate_name_ignoring_case(direction):
    response = _create(name=direction["name"].upper())

    assert response.status_code == 409
    assert response.json()["code"] == "DIRECTION_NAME_TAKEN"


def test_create_direction_rejects_short_name(admin):
    response = _create(name="a")

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


# --- Зміна ---


def test_patch_direction_updates_name_and_description(direction):
    new_name = _unique_name()

    response = client.patch(
        f"{DIRECTIONS_URL}/{direction['id']}",
        json={"name": new_name, "description": "новий опис"},
        headers=AUTH,
    )

    assert response.status_code == 200
    assert response.json()["name"] == new_name
    assert response.json()["description"] == "новий опис"


def test_patch_direction_with_same_values_changes_nothing(direction):
    response = client.patch(
        f"{DIRECTIONS_URL}/{direction['id']}",
        json={"name": direction["name"], "description": direction["description"]},
        headers=AUTH,
    )

    assert response.status_code == 200
    assert response.json() == direction


def test_patch_direction_null_description_clears_it(direction):
    response = client.patch(f"{DIRECTIONS_URL}/{direction['id']}", json={"description": None}, headers=AUTH)

    assert response.status_code == 200
    assert response.json()["description"] is None


def test_patch_direction_rejects_name_taken_by_another(direction):
    other = _create().json()

    response = client.patch(f"{DIRECTIONS_URL}/{other['id']}", json={"name": direction["name"]}, headers=AUTH)

    assert response.status_code == 409
    assert response.json()["code"] == "DIRECTION_NAME_TAKEN"
    _delete(other["id"])


def test_patch_unknown_direction_is_404(admin):
    response = client.patch(f"{DIRECTIONS_URL}/999999", json={"name": "Whatever"}, headers=AUTH)

    assert response.status_code == 404
    assert response.json()["code"] == "DIRECTION_NOT_FOUND"


def test_patch_direction_rejects_non_positive_id(admin):
    response = client.patch(f"{DIRECTIONS_URL}/0", json={"name": "Whatever"}, headers=AUTH)

    assert response.status_code == 422


# --- Видалення ---


def test_delete_direction_then_it_is_gone(admin):
    created = _create().json()

    first = _delete(created["id"])
    second = _delete(created["id"])

    assert first.status_code == 204
    assert second.status_code == 404


def test_delete_direction_in_use_is_409(direction):
    course_id, old_ids = _first_course()
    _set_directions(course_id, [*old_ids, direction["id"]])
    try:
        response = _delete(direction["id"])

        assert response.status_code == 409
        assert response.json()["code"] == "DIRECTION_IN_USE"
    finally:
        _set_directions(course_id, old_ids)


# --- Прив'язка дисципліни до напрямків ---


def test_set_discipline_directions_replaces_list(direction):
    course_id, old_ids = _first_course()
    try:
        response = _set_directions(course_id, [direction["id"], direction["id"]])

        assert response.status_code == 200
        assert _first_course()[1] == [direction["id"]]
    finally:
        _set_directions(course_id, old_ids)


def test_set_discipline_directions_empty_list_makes_free_elective(admin):
    course_id, old_ids = _first_course()
    try:
        response = _set_directions(course_id, [])

        assert response.status_code == 200
        assert _first_course()[1] == []
    finally:
        _set_directions(course_id, old_ids)


def test_set_discipline_directions_unknown_discipline_is_404(admin):
    response = _set_directions(999999, [])

    assert response.status_code == 404
    assert response.json()["code"] == "DISCIPLINE_NOT_FOUND"


def test_set_discipline_directions_unknown_direction_is_422(admin):
    course_id, _ = _first_course()

    response = _set_directions(course_id, [999999])

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
