"""
Модульні тести обробки документа деканату (src/api/routes/deanery.py) без БД і без реального парсера.

Парсер `extract_courses` поки заглушка, тому його підміняють через patch; сесію БД замінює MagicMock.

Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: pytest, ruff.
"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.api.routes import deanery
from src.api.routes.deanery import ParsedCourse, _add_history, _mark_failed, _store_courses, current_academic_year
from src.db import enums as db_enums


@pytest.fixture
def patch_session_factory(fake_session):
    """Підміняє session_factory()() так, щоб `with ... as db` віддавав fake_session."""
    factory = MagicMock()
    factory.return_value.return_value.__enter__.return_value = fake_session
    with patch.object(deanery, "session_factory", factory):
        yield fake_session


def _document(**overrides):
    data = {
        "id": 5,
        "student_id": 42,
        "academic_year": 2025,
        "content": b"%PDF",
        "mime_type": db_enums.DocumentMimeType.PDF,
        "parse_status": db_enums.DocumentParseStatus.PENDING,
        "parse_error": None,
        "normative_courses": [],
    }
    data.update(overrides)
    return SimpleNamespace(**data)


# --- current_academic_year ---


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 8, 31), 2025),
        (date(2026, 9, 1), 2026),
        (date(2026, 12, 31), 2026),
        (date(2027, 1, 1), 2026),
    ],
)
def test_current_academic_year_changes_on_first_of_september(today, expected):
    assert current_academic_year(today) == expected


def test_current_academic_year_uses_system_date_by_default():
    with patch.object(deanery, "date") as fake_date:
        fake_date.today.return_value = date(2030, 10, 5)
        assert current_academic_year() == 2030


# --- _mark_failed ---


def test_mark_failed_saves_status_and_truncates_message(fake_session):
    document = _document()
    fake_session.get.return_value = document

    _mark_failed(fake_session, 5, "x" * 1500)

    assert document.parse_status == db_enums.DocumentParseStatus.FAILED
    assert len(document.parse_error) == 1000
    fake_session.commit.assert_called_once()


def test_mark_failed_ignores_missing_document(fake_session):
    fake_session.get.return_value = None

    _mark_failed(fake_session, 404, "помилка")

    fake_session.commit.assert_not_called()


# --- process_document ---


def test_process_document_returns_when_document_is_missing(patch_session_factory):
    patch_session_factory.get.return_value = None

    with patch.object(deanery, "extract_courses") as extract:
        deanery.process_document(404)

    extract.assert_not_called()
    patch_session_factory.commit.assert_not_called()


def test_process_document_stores_parsed_courses_and_commits(patch_session_factory):
    document = _document()
    patch_session_factory.get.return_value = document
    parsed = [ParsedCourse("Алгоритми", 1, 5.0)]

    with (
        patch.object(deanery, "extract_courses", return_value=parsed) as extract,
        patch.object(deanery, "_store_courses") as store,
    ):
        deanery.process_document(5)

    extract.assert_called_once_with(document.content, document.mime_type)
    store.assert_called_once_with(patch_session_factory, document, parsed)
    patch_session_factory.commit.assert_called_once()
    patch_session_factory.rollback.assert_not_called()


def test_process_document_marks_failed_when_parser_is_not_implemented(patch_session_factory):
    document = _document()
    patch_session_factory.get.return_value = document

    # Справжній extract_courses поки кидає NotImplementedError: це й є очікуваний шлях
    deanery.process_document(5)

    patch_session_factory.rollback.assert_called_once()
    assert document.parse_status == db_enums.DocumentParseStatus.FAILED
    assert "не реалізовано" in document.parse_error


def test_process_document_hides_unexpected_error_details(patch_session_factory, caplog):
    document = _document()
    patch_session_factory.get.return_value = document

    with patch.object(deanery, "extract_courses", side_effect=RuntimeError("секрет у стеку")):
        deanery.process_document(5)

    patch_session_factory.rollback.assert_called_once()
    assert document.parse_error == "Не вдалося розпізнати документ"
    assert "секрет" not in document.parse_error
    assert "Не вдалося опрацювати документ деканату 5" in caplog.text


# --- _store_courses ---


def test_store_courses_skips_invalid_rows_and_links_catalog(fake_session):
    catalog_course = SimpleNamespace(id=11, title_normalized="алгоритми", title="Алгоритми")
    fake_session.scalars.return_value = [catalog_course, SimpleNamespace(id=12, title_normalized="алгоритми")]
    document = _document(academic_year=2026)
    parsed = [
        ParsedCourse("Алгоритми", 1, 5.0),
        ParsedCourse("Невідома дисципліна", 2, 3.0),
        ParsedCourse("   ", 1, 3.0),  # порожня назва
        ParsedCourse("Нульові кредити", 1, 0),
        ParsedCourse("Поза триместрами", 4, 3.0),
    ]

    with patch.object(deanery, "current_academic_year", return_value=2026):
        _store_courses(fake_session, document, parsed)

    entries = document.normative_courses
    assert [(e.raw_title, e.course_id) for e in entries] == [("Алгоритми", 11), ("Невідома дисципліна", None)]
    assert document.parse_status == db_enums.DocumentParseStatus.PARSED
    assert document.parse_error is None


def test_store_courses_without_valid_rows_does_not_query_catalog(fake_session):
    document = _document(academic_year=2026)

    with patch.object(deanery, "current_academic_year", return_value=2026):
        _store_courses(fake_session, document, [ParsedCourse("", 1, 3.0)])

    fake_session.scalars.assert_not_called()
    assert document.normative_courses == []


# --- _add_history ---


def test_add_history_skips_current_and_future_academic_year(fake_session):
    with patch.object(deanery, "current_academic_year", return_value=2025):
        _add_history(fake_session, _document(academic_year=2025), [ParsedCourse("Алгоритми", 1, 5.0)], {})

    fake_session.get.assert_not_called()
    fake_session.add.assert_not_called()


@pytest.mark.parametrize(
    "profile",
    [None, SimpleNamespace(course_year=None), SimpleNamespace(course_year=1)],
    ids=["no-profile", "no-course-year", "year-before-first-course"],
)
def test_add_history_skips_when_course_year_cannot_be_derived(fake_session, profile):
    fake_session.get.return_value = profile

    with patch.object(deanery, "current_academic_year", return_value=2026):
        _add_history(fake_session, _document(academic_year=2024), [ParsedCourse("Алгоритми", 1, 5.0)], {})

    fake_session.add.assert_not_called()


def test_add_history_adds_unverified_records_and_skips_already_taken(fake_session):
    fake_session.get.return_value = SimpleNamespace(course_year=3)
    fake_session.scalars.return_value = [11]  # курс 11 студент уже має в історії
    known = SimpleNamespace(id=11, title="Алгоритми")
    other = SimpleNamespace(id=12, title="Бази даних")
    catalog = {"алгоритми": known, "бази даних": other}
    parsed = [
        ParsedCourse("Алгоритми", 1, 5.0),
        ParsedCourse("Бази даних", 2, 4.0),
        ParsedCourse("Не з каталогу", 3, 3.0),
    ]

    with patch.object(deanery, "current_academic_year", return_value=2026):
        _add_history(fake_session, _document(academic_year=2025), parsed, catalog)

    records = [call.args[0] for call in fake_session.add.call_args_list]
    assert [(r.course_id, r.title) for r in records] == [(12, "Бази даних"), (None, "Не з каталогу")]
    assert all(r.course_year == 2 and r.verified is False for r in records)
    assert all(r.source == db_enums.RecordSource.DEANERY_DOCUMENT for r in records)
