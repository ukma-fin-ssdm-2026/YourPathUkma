"""
Тести мінімуму кредитів за навчальний рік (AGENTS.md §4: мінімум 57–60 кредитів/рік).

Використання ШІ: план TDD-циклу складено з Claude (Anthropic). Перевірка: кожен тест спершу
запущено й побачено падіння (RED), потім проходження після мінімального коду (GREEN).
"""

import pytest

from src.services.plan_rules import check_annual_minimum


@pytest.mark.parametrize(
    ("credits", "expected_codes"),
    [(60, []), (50, ["ANNUAL_MINIMUM_NOT_MET"])],
    ids=["enough", "too-few"],
)
def test_annual_minimum(credits, expected_codes):
    assert [v.code for v in check_annual_minimum(credits)] == expected_codes

def test_message_shows_missing_credits():
    violations = check_annual_minimum(50)
    assert "бракує 7" in violations[0].message

def test_negative_credits_are_rejected():
    with pytest.raises(ValueError):
        check_annual_minimum(-1)
