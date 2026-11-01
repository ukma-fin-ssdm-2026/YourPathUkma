"""
Тести перетворення ParsedCourse у payload модерації.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest.
"""

from pathlib import Path

import pytest

from src.api.routes.admin.sync import CoursePayload
from src.parser.mapper import MappingError, course_to_payload
from src.parser.models import ParsedCourse, Semester, Specialty
from src.parser.parsers.catalog import CatalogParser

FIXTURES = Path(__file__).parent / "fixtures" / "saz"


def _course(**overrides) -> ParsedCourse:
    base = dict(
        saz_code="1",
        saz_internal_id="10",
        title="Курс",
        credits=4.0,
        recommended_year=2,
        semesters=[Semester(number=3, season="Осінь", credits=4.0)],
        specialties=[Specialty("Інженерія ПЗ", "Професійно-орієнтована")],
    )
    return ParsedCourse(**{**base, **overrides})


@pytest.fixture(scope="module")
def parsed():
    html = (FIXTURES / "catalog_filtered_26.html").read_text(encoding="utf-8")
    return {c.saz_code: c for c in CatalogParser().parse(html).courses}


def test_basic_mapping():
    payload = course_to_payload(_course())
    assert payload["trimester"] == 1
    assert payload["kind"] == "elective"
    assert payload["credits"] == 4.0
    assert payload["happened"] is True


@pytest.mark.parametrize("season, number", [("Осінь", 1), ("Весна", 2), ("Літо", 3)])
def test_trimester_from_first_semester(season, number):
    course = _course(semesters=[Semester(1, season, 3.0), Semester(2, "Весна", 3.0)])
    assert course_to_payload(course)["trimester"] == number


def test_kind_normative_only_if_mandatory_for_all_specialties():
    mandatory = [Specialty("А", "Обов`язкова"), Specialty("Б", "Обов’язкова")]
    assert course_to_payload(_course(specialties=mandatory))["kind"] == "normative"
    mixed = mandatory + [Specialty("В", "Вільного вибору")]
    assert course_to_payload(_course(specialties=mixed))["kind"] == "elective"
    assert course_to_payload(_course(specialties=[]))["kind"] == "elective"


def test_long_text_is_truncated():
    payload = course_to_payload(_course(title="я" * 500, description="а" * 30000))
    assert len(payload["title"]) == 300
    assert len(payload["description"]) == 20000


def test_missing_description_becomes_empty_string():
    assert course_to_payload(_course(description=None))["description"] == ""


@pytest.mark.parametrize(
    "overrides",
    [
        {"semesters": []},
        {"credits": None},
        {"recommended_year": None},
        {"recommended_year": 5},
    ],
)
def test_unmappable_courses_raise(overrides):
    with pytest.raises(MappingError):
        course_to_payload(_course(**overrides))


def test_all_fixture_courses_pass_course_payload(parsed):
    assert parsed
    for course in parsed.values():
        CoursePayload.model_validate(course_to_payload(course))


def test_multi_semester_fixture(parsed):
    payload = course_to_payload(parsed["362856"])
    assert payload["kind"] == "normative"
    assert payload["trimester"] == 1
    assert len(payload["semesters"]) == 2
