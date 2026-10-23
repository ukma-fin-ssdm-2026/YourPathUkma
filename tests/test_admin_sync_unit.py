"""
Модульні тести допоміжних функцій модерації (src/api/routes/admin/sync.py) без БД та HTTP.

Сесія БД підроблена (MagicMock із spec=Session), елементи модерації це прості об'єкти, тож тест перевіряє
лише логіку функцій: які запити вони роблять і що змінюють.

Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: pytest, ruff.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.api.common import ApiError
from src.api.routes.admin.sync import (
    CoursePayload,
    _apply_change,
    _check_change,
    _item_response,
    _job_response,
    _ref,
    _users_by_id,
)
from src.db import enums as db_enums

ADD = db_enums.ModerationChangeType.ADD
UPDATE = db_enums.ModerationChangeType.UPDATE
REMOVE = db_enums.ModerationChangeType.REMOVE

FULL_PAYLOAD = {
    "saz_code": "SAZ-900",
    "title": "Тестова дисципліна",
    "credits": 4.0,
    "trimester": 2,
    "recommended_year": 3,
    "kind": "elective",
}


def _payload_fields(error: ApiError) -> set:
    return {detail.field for detail in error.details}


# --- _check_change ---


@pytest.mark.parametrize("course_id", [None, 7])
def test_check_change_remove_without_course_in_catalog(fake_session, make_item, course_id):
    fake_session.get.return_value = None
    item = make_item(change_type=REMOVE, course_id=course_id)

    with pytest.raises(ApiError) as error:
        _check_change(fake_session, item)

    assert error.value.status_code == 422
    assert error.value.code == "MODERATION_PAYLOAD_INVALID"
    assert "архівації" in error.value.message


def test_check_change_remove_returns_existing_course(fake_session, make_item):
    course = SimpleNamespace(id=7)
    fake_session.get.return_value = course

    result = _check_change(fake_session, make_item(change_type=REMOVE))

    assert result == (course, None)


def test_check_change_add_lists_every_missing_field(fake_session, make_item):
    item = make_item(change_type=ADD, payload={"title": "Назва", "credits": 3})

    with pytest.raises(ApiError) as error:
        _check_change(fake_session, item)

    assert _payload_fields(error.value) == {"saz_code", "trimester", "recommended_year", "kind"}
    fake_session.scalar.assert_not_called()


def test_check_change_add_rejects_duplicate_saz_code(fake_session, make_item):
    fake_session.scalar.return_value = 55  # курс із таким saz_code вже існує
    item = make_item(change_type=ADD, payload=FULL_PAYLOAD, course_id=None)

    with pytest.raises(ApiError) as error:
        _check_change(fake_session, item)

    assert _payload_fields(error.value) == {"saz_code"}
    assert "SAZ-900" in error.value.details[0].message


def test_check_change_add_returns_validated_payload(fake_session, make_item):
    fake_session.scalar.return_value = None
    item = make_item(change_type=ADD, payload=FULL_PAYLOAD, course_id=None)

    course, data = _check_change(fake_session, item)

    assert course is None
    assert isinstance(data, CoursePayload)
    assert data.saz_code == "SAZ-900"
    assert data.kind == db_enums.CourseKind.ELECTIVE


@pytest.mark.parametrize(
    ("payload", "bad_field"),
    [
        ({"credits": -1}, "credits"),
        ({"credits": 31}, "credits"),
        ({"trimester": 4}, "trimester"),
        ({"recommended_year": 0}, "recommended_year"),
        ({"title": "a"}, "title"),
        ({"kind": "unknown"}, "kind"),
    ],
)
def test_check_change_update_rejects_values_outside_limits(fake_session, make_item, payload, bad_field):
    with pytest.raises(ApiError) as error:
        _check_change(fake_session, make_item(payload=payload))

    assert bad_field in _payload_fields(error.value)
    assert error.value.message == "Некоректний payload елемента модерації"


def test_check_change_update_without_course_in_catalog(fake_session, make_item):
    fake_session.get.return_value = None

    with pytest.raises(ApiError) as error:
        _check_change(fake_session, make_item(payload={"credits": 5}))

    assert "оновлення" in error.value.message


def test_check_change_update_returns_course_and_payload(fake_session, make_item):
    course = SimpleNamespace(id=7)
    fake_session.get.return_value = course

    result_course, data = _check_change(fake_session, make_item(payload={"credits": 5, "extra": "ignored"}))

    assert result_course is course
    assert data.credits == 5


def test_check_change_treats_empty_payload_as_empty_update(fake_session, make_item):
    fake_session.get.return_value = SimpleNamespace(id=7)

    _, data = _check_change(fake_session, make_item(payload=None))

    assert data == CoursePayload()


# --- _apply_change ---


def test_apply_change_add_creates_published_course(fake_session, make_item):
    item = make_item(change_type=ADD, payload=FULL_PAYLOAD, course_id=None, sync_job_id=12)
    data = CoursePayload.model_validate(FULL_PAYLOAD)
    fake_session.add.side_effect = lambda course: setattr(course, "id", 99)

    _apply_change(fake_session, item, None, data)

    added = fake_session.add.call_args.args[0]
    assert added.saz_code == "SAZ-900"
    assert added.publication_status == db_enums.PublicationStatus.PUBLISHED
    assert added.last_sync_job_id == 12
    assert added.description == ""
    fake_session.flush.assert_called_once()
    assert item.course_id == 99


def test_apply_change_update_changes_only_given_fields(fake_session, make_item):
    course = SimpleNamespace(
        title="Стара назва",
        title_normalized="стара назва",
        description="Опис",
        credits=3.0,
        trimester=db_enums.Trimester.AUTUMN,
        recommended_year=2,
        kind=db_enums.CourseKind.ELECTIVE,
        last_sync_job_id=None,
    )

    _apply_change(fake_session, make_item(sync_job_id=8), course, CoursePayload(credits=5.0))

    assert course.credits == 5.0
    assert course.title == "Стара назва"
    assert course.description == "Опис"
    assert course.trimester == db_enums.Trimester.AUTUMN
    assert course.last_sync_job_id == 8
    fake_session.add.assert_not_called()


def test_apply_change_update_applies_every_field(fake_session, make_item):
    course = SimpleNamespace(
        title="x",
        title_normalized="x",
        description="",
        credits=1.0,
        trimester=db_enums.Trimester.AUTUMN,
        recommended_year=1,
        kind=db_enums.CourseKind.ELECTIVE,
        last_sync_job_id=None,
    )
    data = CoursePayload(
        title="Нова назва",
        description="Новий опис",
        credits=6.0,
        trimester=3,
        recommended_year=4,
        kind=db_enums.CourseKind.NORMATIVE,
    )

    _apply_change(fake_session, make_item(), course, data)

    assert (course.title, course.description, course.credits) == ("Нова назва", "Новий опис", 6.0)
    assert course.title_normalized == "нова назва"
    assert course.trimester == db_enums.Trimester.SUMMER
    assert (course.recommended_year, course.kind) == (4, db_enums.CourseKind.NORMATIVE)


def test_apply_change_remove_archives_course(fake_session, make_item):
    course = SimpleNamespace(publication_status=db_enums.PublicationStatus.PUBLISHED, last_sync_job_id=None)

    _apply_change(fake_session, make_item(change_type=REMOVE, sync_job_id=4), course, None)

    assert course.publication_status == db_enums.PublicationStatus.ARCHIVED
    assert course.last_sync_job_id == 4


# --- допоміжні перетворення ---


def test_users_by_id_skips_query_without_ids(fake_session):
    assert _users_by_id(fake_session, {None}) == {}
    fake_session.scalars.assert_not_called()


def test_users_by_id_indexes_found_users(fake_session):
    admin = SimpleNamespace(id=1, full_name="Адміністратор")
    fake_session.scalars.return_value = [admin]

    assert _users_by_id(fake_session, {1, None}) == {1: admin}


@pytest.mark.parametrize("user_id", [None, 404])
def test_ref_returns_none_for_unknown_user(user_id):
    assert _ref({1: SimpleNamespace(id=1, full_name="Адмін")}, user_id) is None


def test_ref_builds_user_reference():
    assert _ref({1: SimpleNamespace(id=1, full_name="Адмін")}, 1).full_name == "Адмін"


def test_job_response_copies_fields_and_resolves_initiator():
    job = SimpleNamespace(
        id=31,
        source=db_enums.SyncSource.SAZ_CATALOG,
        initiator=db_enums.SyncInitiator.ADMIN,
        initiated_by=1,
        status=db_enums.SyncJobStatus.QUEUED,
        started_at=datetime(2026, 10, 1, 12, 0),
        finished_at=None,
        added_count=2,
        updated_count=3,
        error_message=None,
    )

    response = _job_response(job, {1: SimpleNamespace(id=1, full_name="Адмін")})

    assert (response.id, response.added_count, response.updated_count) == (31, 2, 3)
    assert response.initiated_by.full_name == "Адмін"


def test_item_response_defaults_payload_to_empty_dict():
    item = SimpleNamespace(
        id=501,
        sync_job_id=31,
        course_id=None,
        change_type=ADD,
        payload=None,
        diff=None,
        status=db_enums.ModerationStatus.PENDING,
        reviewed_by=None,
        reviewed_at=None,
    )

    response = _item_response(item, {})

    assert response.payload == {}
    assert response.reviewed_by is None
