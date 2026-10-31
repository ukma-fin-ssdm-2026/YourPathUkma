"""
TP-18: модульні тести перетворення курсу з БД на модель API `to_discipline` (src/api/routes/disciplines.py).

Без HTTP і без БД: курс, викладачі й напрямки — SimpleNamespace з тими самими атрибутами, що й ORM-моделі.

Використання ШІ: файл створено за допомогою Claude (Claude Code) за рядком TP-18 у docs/validation/test-plan.md.
Перевірка: pytest; тести падають, якщо в to_discipline змінити роздільник викладачів або джерело directions.
"""

from types import SimpleNamespace

import pytest

from src.api.routes.disciplines import Discipline, DisciplineType, to_discipline
from src.db import enums as db_enums


def _course(instructors=("Петренко І. М.",), directions=("Data Science",), **overrides):
    data = {
        "id": 101,
        "title": "Функціональне програмування",
        "description": "Основи функціональної парадигми.",
        "kind": db_enums.CourseKind.ELECTIVE,
        "recommended_year": 2,
        "trimester": db_enums.Trimester.SPRING,
        "credits": 5.0,
        "course_instructors": [SimpleNamespace(instructor=SimpleNamespace(full_name=name)) for name in instructors],
        "directions": [SimpleNamespace(name=name) for name in directions],
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_to_discipline_maps_course_fields():
    # Arrange
    course = _course()

    # Act
    discipline = to_discipline(course)

    # Assert
    assert isinstance(discipline, Discipline)
    assert discipline.model_dump() == {
        "id": 101,
        "title": "Функціональне програмування",
        "description": "Основи функціональної парадигми.",
        "discipline_type": DisciplineType.ELECTIVE,
        "instructor": "Петренко І. М.",
        "recommended_year": 2,
        "trimester": 2,  # у БД назва триместру, в API — число
        "credits": 5.0,
        "directions": ["Data Science"],
    }


@pytest.mark.parametrize(
    "instructors, expected",
    [
        pytest.param(("Петренко І. М.", "Коваль О. В."), "Петренко І. М., Коваль О. В.", id="two"),
        pytest.param(("А. А.", "Б. Б.", "В. В."), "А. А., Б. Б., В. В.", id="three"),
        pytest.param((), "", id="none"),
    ],
)
def test_to_discipline_joins_instructors_with_comma(instructors, expected):
    # Arrange
    course = _course(instructors=instructors)

    # Act
    discipline = to_discipline(course)

    # Assert
    assert discipline.instructor == expected


def test_to_discipline_free_choice_has_empty_directions():
    # Arrange: дисципліна без прив'язки до напрямків — вільний вибір для будь-якого студента
    course = _course(directions=())

    # Act
    discipline = to_discipline(course)

    # Assert
    assert discipline.directions == []
    assert discipline.discipline_type == DisciplineType.ELECTIVE


def test_to_discipline_keeps_all_directions_in_order():
    # Arrange
    course = _course(directions=("Software Engineering", "Data Science"))

    # Act
    discipline = to_discipline(course)

    # Assert
    assert discipline.directions == ["Software Engineering", "Data Science"]
