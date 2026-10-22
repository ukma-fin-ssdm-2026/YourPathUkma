from src.services.email_domain import is_ukma_email


def test_accepts_ukma_email():
    assert is_ukma_email("student@ukma.edu.ua") is True


def test_is_case_insensitive():
    assert is_ukma_email("Student@UKMA.EDU.UA") is True


def test_rejects_empty_local_part():
    assert is_ukma_email("@ukma.edu.ua") is False
