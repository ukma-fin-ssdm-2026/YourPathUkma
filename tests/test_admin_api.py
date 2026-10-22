"""
Тести адмінських ендпоїнтів від імені адміністратора (seed: id 1) через фікстуру admin_client.

Покривають користувачів, напрямки й журнал аудиту: фільтри, 404, 409 і запис змін в audit_log.
Дані з seed спільні для всієї сесії, тому тести, що змінюють БД, прибирають за собою або створюють унікальні записи.

Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: pytest, ruff.
"""

import itertools

import pytest
from sqlalchemy import select

from src.db import enums as db_enums
from src.db.models.admin import AuditLog
from src.db.models.catalog import Course
from src.db.models.history import AcademicRecord
from src.db.session import session_factory

_names = itertools.count(1)


def _unique_name(prefix="Напрямок"):
    return f"{prefix} {next(_names)} {id(_names) % 1000}"


def _audit_actions(action):
    with session_factory()() as db:
        return list(db.scalars(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)))


# --- користувачі ---


def test_list_users_returns_seeded_users(admin_client):
    response = admin_client.get("/api/v1/admin/users")

    body = response.json()
    assert response.status_code == 200
    assert {u["id"] for u in body["users"]} >= {1, 7, 42}
    assert body["pagination"]["total"] >= 3


@pytest.mark.parametrize(
    ("params", "expected_ids"),
    [
        ({"role": "admin"}, {1}),
        ({"course_year": 3}, {7}),
        ({"q": "student@ukma"}, {7, 42}),
    ],
    ids=["by-role", "by-course-year", "by-email-substring"],
)
def test_list_users_filters(admin_client, params, expected_ids):
    response = admin_client.get("/api/v1/admin/users", params=params)

    assert response.status_code == 200
    assert {u["id"] for u in response.json()["users"]} == expected_ids


@pytest.mark.parametrize(("flag", "expected"), [(True, set()), (False, {7, 42})])
def test_list_users_onboarding_filter(admin_client, flag, expected):
    response = admin_client.get("/api/v1/admin/users", params={"onboarding_required": flag})

    assert {u["id"] for u in response.json()["users"]} == expected


def test_list_users_paginates(admin_client):
    response = admin_client.get("/api/v1/admin/users", params={"limit": 1, "offset": 0})

    body = response.json()
    assert len(body["users"]) == 1
    assert body["pagination"]["has_more"] is True


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"q": "a"}, {"course_year": 5}])
def test_list_users_rejects_invalid_query(admin_client, params):
    assert admin_client.get("/api/v1/admin/users", params=params).status_code == 422


def test_get_user_returns_profile_with_dates(admin_client):
    response = admin_client.get("/api/v1/admin/users/42")

    body = response.json()
    assert response.status_code == 200
    assert body["email"] == "student@ukma.edu.ua"
    assert "created_at" in body


def test_get_user_unknown_id_is_404(admin_client):
    response = admin_client.get("/api/v1/admin/users/9999")

    assert response.status_code == 404
    assert response.json()["code"] == "USER_NOT_FOUND"


def test_patch_user_changes_course_year_and_writes_audit(admin_client):
    before = len(_audit_actions("user.update"))

    response = admin_client.patch("/api/v1/admin/users/7", json={"student": {"course_year": 4}})

    assert response.status_code == 200
    assert response.json()["student"]["course_year"] == 4
    assert response.json()["student"]["course_year_source"] == "admin"
    entries = _audit_actions("user.update")
    assert len(entries) == before + 1
    assert entries[-1].new_value["course_year"] == 4
    admin_client.patch("/api/v1/admin/users/7", json={"student": {"course_year": 3}})  # повертаємо seed


def test_patch_user_without_changes_writes_no_audit(admin_client):
    before = len(_audit_actions("user.update"))

    response = admin_client.patch("/api/v1/admin/users/42", json={"role": "student"})

    assert response.status_code == 200
    assert len(_audit_actions("user.update")) == before


def test_patch_user_cannot_change_own_role(admin_client):
    response = admin_client.patch("/api/v1/admin/users/1", json={"role": "student"})

    assert response.status_code == 409
    assert response.json()["code"] == "CANNOT_CHANGE_OWN_ROLE"


def test_patch_user_unknown_id_is_404(admin_client):
    assert admin_client.patch("/api/v1/admin/users/9999", json={"role": "admin"}).status_code == 404


@pytest.mark.parametrize("student", [{"course_year": 0}, {"course_year": 5}, {"specialty": "a"}])
def test_patch_user_rejects_invalid_student_fields(admin_client, student):
    assert admin_client.patch("/api/v1/admin/users/42", json={"student": student}).status_code == 422


def test_user_history_is_empty_for_student_without_records(admin_client):
    response = admin_client.get("/api/v1/admin/users/7/academic-history")

    assert response.status_code == 200
    assert response.json() == {"years": []}


def test_user_history_unknown_user_is_404(admin_client):
    assert admin_client.get("/api/v1/admin/users/9999/academic-history").status_code == 404


def test_verify_records_splits_verified_and_skipped(admin_client):
    with session_factory()() as db:
        record = AcademicRecord(
            student_id=7,
            academic_year=2025,
            course_year=2,
            title="Тестовий запис",
            credits=3.0,
            trimester=db_enums.Trimester.AUTUMN,
            category=db_enums.AcademicCategory.FREE_CHOICE,
            source=db_enums.RecordSource.SELF_DECLARED,
        )
        db.add(record)
        db.commit()
        record_id = record.id

    response = admin_client.post(
        "/api/v1/admin/users/7/academic-history/verify", json={"record_ids": [record_id, record_id, 999999]}
    )

    body = response.json()
    assert response.status_code == 200
    assert body["verified"] == [record_id]
    assert body["skipped"] == [{"id": 999999, "code": "RECORD_NOT_FOUND"}]
    again = admin_client.post("/api/v1/admin/users/7/academic-history/verify", json={"record_ids": [record_id]})
    assert again.json()["skipped"] == [{"id": record_id, "code": "RECORD_NOT_VERIFIABLE"}]
    with session_factory()() as db:  # не лишаємо запис у спільній БД
        db.delete(db.get(AcademicRecord, record_id))
        db.commit()


def test_verify_records_rejects_empty_list(admin_client):
    response = admin_client.post("/api/v1/admin/users/7/academic-history/verify", json={"record_ids": []})

    assert response.status_code == 422


# --- напрямки ---


def test_create_direction_and_reject_duplicate_name(admin_client):
    name = _unique_name()

    created = admin_client.post("/api/v1/admin/directions", json={"name": name, "description": "Опис"})
    duplicate = admin_client.post("/api/v1/admin/directions", json={"name": f"  {name.upper()}  "})

    assert created.status_code == 201
    assert created.json()["name"] == name
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "DIRECTION_NAME_TAKEN"
    admin_client.delete(f"/api/v1/admin/directions/{created.json()['id']}")


def test_patch_direction_updates_name_and_clears_description(admin_client):
    direction = admin_client.post("/api/v1/admin/directions", json={"name": _unique_name(), "description": "Старий"})
    direction_id = direction.json()["id"]
    new_name = _unique_name("Перейменований")

    renamed = admin_client.patch(f"/api/v1/admin/directions/{direction_id}", json={"name": new_name})
    cleared = admin_client.patch(f"/api/v1/admin/directions/{direction_id}", json={"description": None})

    assert renamed.json()["name"] == new_name
    assert cleared.json()["description"] is None
    assert _audit_actions("direction.update")
    admin_client.delete(f"/api/v1/admin/directions/{direction_id}")


def test_patch_direction_rejects_name_of_another_direction(admin_client):
    first = admin_client.post("/api/v1/admin/directions", json={"name": _unique_name()}).json()
    second = admin_client.post("/api/v1/admin/directions", json={"name": _unique_name()}).json()

    response = admin_client.patch(f"/api/v1/admin/directions/{second['id']}", json={"name": first["name"]})

    assert response.status_code == 409
    for direction in (first, second):
        admin_client.delete(f"/api/v1/admin/directions/{direction['id']}")


def test_patch_direction_without_changes_keeps_audit_clean(admin_client):
    direction = admin_client.post("/api/v1/admin/directions", json={"name": _unique_name()}).json()
    before = len(_audit_actions("direction.update"))

    response = admin_client.patch(f"/api/v1/admin/directions/{direction['id']}", json={"name": direction["name"]})

    assert response.status_code == 200
    assert len(_audit_actions("direction.update")) == before
    admin_client.delete(f"/api/v1/admin/directions/{direction['id']}")


def test_patch_and_delete_unknown_direction_are_404(admin_client):
    assert admin_client.patch("/api/v1/admin/directions/9999", json={"name": "Назва"}).status_code == 404
    assert admin_client.delete("/api/v1/admin/directions/9999").status_code == 404


def test_delete_direction_in_use_is_409(admin_client):
    response = admin_client.delete("/api/v1/admin/directions/1")  # прив'язаний до дисциплін у seed

    assert response.status_code == 409
    assert response.json()["code"] == "DIRECTION_IN_USE"


def test_delete_unused_direction_succeeds_and_is_audited(admin_client):
    direction = admin_client.post("/api/v1/admin/directions", json={"name": _unique_name()}).json()

    response = admin_client.delete(f"/api/v1/admin/directions/{direction['id']}")

    assert response.status_code == 204
    assert _audit_actions("direction.delete")[-1].object_id == direction["id"]


@pytest.mark.parametrize("body", [{"name": "a"}, {"name": "x" * 51}, {}])
def test_create_direction_rejects_invalid_body(admin_client, body):
    assert admin_client.post("/api/v1/admin/directions", json=body).status_code == 422


def test_set_discipline_directions_replaces_list_and_audits(admin_client):
    with session_factory()() as db:
        original_ids = [d.id for d in db.get(Course, 101).directions]

    try:
        response = admin_client.put("/api/v1/admin/disciplines/101/directions", json={"direction_ids": []})

        assert response.status_code == 200
        assert response.json()["directions"] == []
        assert _audit_actions("discipline.directions.update")
    finally:
        admin_client.put("/api/v1/admin/disciplines/101/directions", json={"direction_ids": original_ids})
    with session_factory()() as db:
        assert [d.id for d in db.get(Course, 101).directions] == sorted(original_ids)


def test_set_discipline_directions_unknown_discipline_is_404(admin_client):
    response = admin_client.put("/api/v1/admin/disciplines/9999/directions", json={"direction_ids": []})

    assert response.status_code == 404


def test_set_discipline_directions_lists_unknown_direction_ids(admin_client):
    response = admin_client.put("/api/v1/admin/disciplines/101/directions", json={"direction_ids": [9998, 9999]})

    assert response.status_code == 422
    assert [d["field"] for d in response.json()["details"]] == ["direction_ids", "direction_ids"]


# --- журнал аудиту ---


def test_audit_log_lists_entries_newest_first(admin_client):
    admin_client.post("/api/v1/admin/directions", json={"name": _unique_name()})

    response = admin_client.get("/api/v1/admin/audit-log")

    entries = response.json()["audit_log"]
    assert response.status_code == 200
    assert entries
    assert [e["id"] for e in entries] == sorted((e["id"] for e in entries), reverse=True)


@pytest.mark.parametrize(
    "params",
    [
        {"actor_id": 1},
        {"action": "direction.create"},
        {"object_type": "Direction"},
        {"outcome": "allowed"},
        {"from": "2000-01-01T00:00:00", "to": "2999-01-01T00:00:00"},
    ],
    ids=["actor", "action", "object-type", "outcome", "date-range"],
)
def test_audit_log_filters_return_matching_entries(admin_client, params):
    admin_client.post("/api/v1/admin/directions", json={"name": _unique_name()})

    response = admin_client.get("/api/v1/admin/audit-log", params=params)

    assert response.status_code == 200
    assert response.json()["pagination"]["total"] >= 1


def test_audit_log_filter_by_object_id_and_no_matches(admin_client):
    response = admin_client.get("/api/v1/admin/audit-log", params={"object_id": 987654, "action": "plan.read"})

    assert response.status_code == 200
    assert response.json()["audit_log"] == []
    assert response.json()["pagination"]["has_more"] is False


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"outcome": "maybe"}, {"actor_id": 0}])
def test_audit_log_rejects_invalid_query(admin_client, params):
    assert admin_client.get("/api/v1/admin/audit-log", params=params).status_code == 422


def test_audit_entry_returns_old_and_new_values(admin_client):
    created = admin_client.post("/api/v1/admin/directions", json={"name": _unique_name()}).json()
    entry = _audit_actions("direction.create")[-1]

    response = admin_client.get(f"/api/v1/admin/audit-log/{entry.id}")

    assert response.status_code == 200
    assert response.json()["new_value"]["name"] == created["name"]
    assert response.json()["actor"]["id"] == 1
    admin_client.delete(f"/api/v1/admin/directions/{created['id']}")


def test_audit_entry_unknown_id_is_404(admin_client):
    response = admin_client.get("/api/v1/admin/audit-log/99999999")

    assert response.status_code == 404
    assert response.json()["code"] == "AUDIT_ENTRY_NOT_FOUND"
