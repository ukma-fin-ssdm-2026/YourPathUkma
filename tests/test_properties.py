"""Тести на основі властивостей (Hypothesis): правило дублікатів дисциплін у плані.

Використання ШІ: файл створено за допомогою Claude на основі опису.
Перевірка: pytest локально і в CI.
"""

from hypothesis import given
from hypothesis import strategies as st

from src.services import plan_rules

# Малий діапазон ID, щоб повтори траплялися часто
course_ids = st.lists(st.integers(min_value=1, max_value=50), max_size=20)


@given(course_ids)
def test_duplicate_violation_iff_ids_repeat(ids):
    # Act
    violations = plan_rules.check_duplicate_courses(ids)

    # Assert: порушення є тоді й лише тоді, коли в списку є повторюваний ID
    has_repeat = len(set(ids)) != len(ids)
    assert bool(violations) == has_repeat
    assert all(v.code == "DUPLICATE_COURSE" for v in violations)


@given(course_ids)
def test_duplicate_check_does_not_depend_on_order(ids):
    # Act
    original = [v.code for v in plan_rules.check_duplicate_courses(ids)]
    reordered = [v.code for v in plan_rules.check_duplicate_courses(sorted(ids))]

    # Assert
    assert original == reordered
