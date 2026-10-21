"""
Тести classify_load_level: пороги навантаження та валідація входу.

Використання ШІ: тести написано покроково за планом TDD за допомогою Claude (Anthropic).
Перевірка: pytest, ruff, black, ручний огляд.
"""

import pytest

from src.services.load_levels import classify_load_level


@pytest.mark.parametrize(
    "hours, expected",
    [
        (0, "low"),
        (15, "low"),
        (19.9, "low"),
        (20, "medium"),
        (21, "medium"),
        (22.9, "medium"),
        (23, "high"),
        (25, "high"),
    ],
)
def test_classify_load_level(hours, expected):
    assert classify_load_level(hours) == expected


@pytest.mark.parametrize("hours", [-1, -0.1, 25.1, 30])
def test_hours_out_of_range_rejected(hours):
    with pytest.raises(ValueError):
        classify_load_level(hours)


def test_upper_boundary_belongs_to_high():
    """Регресія: 23 год/тиждень уже high; межа не належить medium."""
    assert classify_load_level(23) == "high"
    assert classify_load_level(22.99) == "medium"
