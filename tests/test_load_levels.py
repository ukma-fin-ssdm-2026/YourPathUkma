from src.services.load_levels import classify_load_level


def test_low_load():
    assert classify_load_level(15) == "low"