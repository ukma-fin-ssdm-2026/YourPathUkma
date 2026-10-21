"""
Тести мінімуму кредитів за навчальний рік (AGENTS.md §4: мінімум 57–60 кредитів/рік).

Використання ШІ: план TDD-циклу складено з Claude (Anthropic). Перевірка: кожен тест спершу
запущено й побачено падіння (RED), потім проходження після мінімального коду (GREEN).
"""

from src.services.plan_rules import check_annual_minimum


def test_enough_credits_has_no_violations():
    assert check_annual_minimum(60) == []

def test_too_few_credits_is_violation():
    violations = check_annual_minimum(50)
    assert [v.code for v in violations] == ["ANNUAL_MINIMUM_NOT_MET"]