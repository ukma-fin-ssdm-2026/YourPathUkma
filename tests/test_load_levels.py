import pytest

from src.services.load_levels import classify_load_level


def test_low_load():
    assert classify_load_level(15) == "low"


def test_medium_load():
    assert classify_load_level(21) == "medium"


def test_high_load():
    assert classify_load_level(24) == "high"


def test_negative_hours_rejected():
    with pytest.raises(ValueError):
        classify_load_level(-1)
