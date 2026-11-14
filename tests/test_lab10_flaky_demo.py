"""Демонстрація детектора нестабільних тестів у гілці Лаб 10.

Використання ШІ: Codex додав кероване чергування результатів.
Перевірка: п'ять запусків GitHub Actions на одному коміті.
"""

import os

import pytest


def test_demonstration_alternates_between_pass_and_fail():
    round_number = os.environ.get("LAB10_FLAKY_DEMO_ROUND")
    if round_number is None:
        pytest.skip("Демонстрація запускається вручну у workflow Flaky tests")

    assert int(round_number) % 2 == 1, "Навмисний збій демонстраційного тесту"
