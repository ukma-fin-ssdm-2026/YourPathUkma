"""
Схвалення елемента модерації з викладачами: `instructors` з payload потрапляють у каталог і в GET /disciplines.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest.
"""

import pytest
from sqlalchemy import select

from src.db import enums as db_enums
from src.db.models.admin import ModerationItem, SyncJob
from src.db.models.catalog import Course, Instructor
from src.db.session import session_factory


@pytest.fixture
def job_id():
    with session_factory()() as db:
        job = SyncJob(
            source=db_enums.SyncSource.SAZ_CATALOG,
            initiator=db_enums.SyncInitiator.ADMIN,
            status=db_enums.SyncJobStatus.SUCCEEDED,
        )
        db.add(job)
        db.commit()
        job_id = job.id
    yield job_id
    # Каталог спільний для всіх тестів: прибираємо створене, інакше test_saz_sync побачить «зниклі» дисципліни.
    with session_factory()() as db:
        for course in db.scalars(select(Course).where(Course.saz_code.like("T-90%"))):
            db.delete(course)
        for name in ("маслійчук", "д'яченко", "шевченко", "старий", "новий"):
            for instructor in db.scalars(select(Instructor).where(Instructor.full_name_normalized.like(f"{name}%"))):
                db.delete(instructor)
        db.commit()


def _item(job_id, change_type, payload, course_id=None):
    with session_factory()() as db:
        item = ModerationItem(sync_job_id=job_id, course_id=course_id, change_type=change_type, payload=payload)
        db.add(item)
        db.commit()
        return item.id


def _payload(code, **extra):
    return {
        "saz_code": code,
        "title": "Тестова дисципліна",
        "credits": 4,
        "trimester": 1,
        "recommended_year": 2,
        "kind": "elective",
        **extra,
    }


def test_approve_add_creates_instructors(admin_client, job_id):
    item_id = _item(
        job_id,
        db_enums.ModerationChangeType.ADD,
        _payload("T-9001", instructors=["Маслійчук В.Л., д.і.н.", "Д'яченко Ю.Ю."]),
    )
    response = admin_client.post(f"/api/v1/admin/moderation-items/{item_id}/approve")
    assert response.status_code == 200
    course_id = response.json()["course_id"]

    with session_factory()() as db:
        names = [ci.instructor.full_name for ci in db.get(Course, course_id).course_instructors]
    assert names == ["Маслійчук В.Л., д.і.н.", "Д'яченко Ю.Ю."]

    listed = admin_client.get("/api/v1/disciplines?instructor=Маслійчук").json()["disciplines"]
    assert any(d["id"] == course_id and "Маслійчук" in d["instructor"] for d in listed)


def _approve_add(admin_client, job_id, code, instructors):
    item_id = _item(job_id, db_enums.ModerationChangeType.ADD, _payload(code, instructors=instructors))
    return admin_client.post(f"/api/v1/admin/moderation-items/{item_id}/approve")


def test_existing_instructor_is_reused_case_insensitively(admin_client, job_id):
    first = _approve_add(admin_client, job_id, "T-9002", ["Шевченко Т.Г."])
    second = _approve_add(admin_client, job_id, "T-9003", ["шевченко т.г."])
    assert first.status_code == second.status_code == 200
    with session_factory()() as db:
        assert len(db.scalars(select(Instructor).where(Instructor.full_name_normalized == "шевченко т.г.")).all()) == 1


def test_update_replaces_instructors_and_missing_key_keeps_them(admin_client, job_id):
    added = _approve_add(admin_client, job_id, "T-9004", ["Старий Викладач"]).json()["course_id"]

    keep = _item(job_id, db_enums.ModerationChangeType.UPDATE, {"title": "Нова назва"}, course_id=added)
    assert admin_client.post(f"/api/v1/admin/moderation-items/{keep}/approve").status_code == 200
    with session_factory()() as db:
        assert [ci.instructor.full_name for ci in db.get(Course, added).course_instructors] == ["Старий Викладач"]

    change = _item(job_id, db_enums.ModerationChangeType.UPDATE, {"instructors": ["Новий Викладач"]}, course_id=added)
    assert admin_client.post(f"/api/v1/admin/moderation-items/{change}/approve").status_code == 200
    with session_factory()() as db:
        assert [ci.instructor.full_name for ci in db.get(Course, added).course_instructors] == ["Новий Викладач"]
