import pytest

from src.services import plan_rules


def test_remaining_when_nothing_used():
    assert plan_rules.free_elective_remaining(0.0) == 25.0


def test_remaining_partial():
    assert plan_rules.free_elective_remaining(10.5) == 14.5


def test_remaining_never_negative():
    assert plan_rules.free_elective_remaining(30) == 0.0


def test_negative_used_rejected():
    pytest.raises(ValueError, lambda: plan_rules.free_elective_remaining(-1))
