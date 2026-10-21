from types import SimpleNamespace

import pytest
from pydantic import ValidationError


from src.services import plan_rules


def test_remaining_when_nothing_used():
    assert plan_rules.free_elective_remaining(0.0) == 25.0