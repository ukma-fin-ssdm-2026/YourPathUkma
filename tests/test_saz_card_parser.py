"""
Парсер картки курсу САЗ на очищених фікстурах (без мережі).

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest.
"""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from src.parser.models import Semester, Specialty
from src.parser.parsers.card import CardParseError, parse_card
from src.parser.parsers.catalog import CatalogParser, iter_cards
from src.parser.parsers.utils import clean_text, parse_float, parse_int, split_instructors

FIXTURES = Path(__file__).parent / "fixtures" / "saz"


@pytest.fixture(scope="module")
def page1():
    return CatalogParser().parse((FIXTURES / "catalog_page1.html").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def page26():
    return CatalogParser().parse((FIXTURES / "catalog_filtered_26.html").read_text(encoding="utf-8"))


def by_code(page, code):
    return next(c for c in page.courses if c.saz_code == code)


def test_full_card_fields(page1):
    course = by_code(page1, "363683")
    assert course.title.startswith('"Великий кордон"')
    assert course.saz_internal_id == "65186"  # не збігається з кодом курсу
    assert (course.credits, course.hours, course.recommended_year) == (4.0, 120, 3)
    assert course.faculty == "Факультет гуманітарних наук"
    assert course.department == "Кафедра історії"
    assert course.level == "Бакалавр"
    assert course.academic_year == "2026–2027"
    assert course.instructors == ["Маслійчук В.Л."]  # ступінь «д.і.н.» відкинуто
    assert course.description and "історико-географічна" in course.description
    assert course.specialties == [Specialty("Історія", "Професійно-орієнтована")]
    assert course.semesters == [Semester(6, "Весна", 4.0)]


def test_status_not_happened(page1):
    assert by_code(page1, "363683").happened is False
    assert by_code(page1, "364920").happened is True


def test_optional_instructor_and_description_missing(page1):
    course = by_code(page1, "364920")
    assert course.instructors == []
    assert course.description is None


def test_multi_semester_course(page26):
    course = by_code(page26, "362856")
    assert course.semesters == [Semester(3, "Осінь", 3.5), Semester(4, "Весна", 3.5)]
    assert course.credits == 3.5  # кредити першого семестру


def test_three_seasons_share_semester_number(page26):
    seasons = [(s.season, s.credits) for s in by_code(page26, "365151").semesters]
    assert seasons == [("Осінь", 3.0), ("Весна", 4.0), ("Літо", 2.0)]


def test_many_specialties_keep_type(page26):
    course = by_code(page26, "362856")
    assert len(course.specialties) > 20
    assert {s.type for s in course.specialties} == {"Обов`язкова"}


def test_selected_course_panel_is_parsed():
    # у курсу, обраного студентом, САЗ дає панелі клас panel-info замість panel-default
    html = (FIXTURES / "catalog_page1.html").read_text(encoding="utf-8")
    html = html.replace('class="panel panel-default"', 'class="panel panel-info"', 1)
    assert len(CatalogParser().parse(html).courses) == 20


def test_student_sidebar_is_not_a_card():
    html = (FIXTURES / "catalog_page1.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")
    assert all(p.select_one("div.panel-collapse[id^='course-card-']") for p in iter_cards(soup))


def test_card_without_code_raises():
    soup = BeautifulSoup(
        '<div class="panel"><div class="panel-heading"><h4 class="panel-title">Курс</h4></div>'
        '<div class="panel-collapse" id="course-card-1"><table><tr><th>Факультет</th><td>ФІ</td></tr></table>'
        "</div></div>",
        "lxml",
    )
    with pytest.raises(CardParseError):
        parse_card(soup.select_one("div.panel"))


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Маслійчук В.Л., д.і.н.", ["Маслійчук В.Л."]),
        ("Д'яченко Ю.Ю., Тимкович В.В.", ["Д'яченко Ю.Ю.", "Тимкович В.В."]),
        ("Ковальчук А.А., к.ф.-м.н., доцент", ["Ковальчук А.А."]),
        ("", []),
        (None, []),
    ],
)
def test_split_instructors(raw, expected):
    assert split_instructors(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [("1\xa0712", 1712), ("1 712 записів", 1712), ("37", 37), ("необмежено", None), ("", None), (None, None)],
)
def test_parse_int(raw, expected):
    assert parse_int(raw) == expected


def test_parse_float_and_clean_text():
    assert parse_float("3,5 кред.") == 3.5
    assert parse_float("немає") is None
    assert clean_text("  а\xa0\n б ") == "а б"
