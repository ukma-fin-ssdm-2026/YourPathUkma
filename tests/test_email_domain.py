import pytest

from src.services.email_domain import is_ukma_email


@pytest.mark.parametrize(
    "email",
    ["student@ukma.edu.ua", "Student@UKMA.EDU.UA"],
    ids=["lowercase", "uppercase"],
)
def test_accepts_ukma_email(email):
    assert is_ukma_email(email) is True


@pytest.mark.parametrize(
    "email",
    [
        "@ukma.edu.ua",
        "a@b@ukma.edu.ua",
        "student@gmail.com",
        "student@mail.ukma.edu.ua",
        "student@evil-ukma.edu.ua",
        "student@ukma.edu.ua.evil.com",
        "student.ukma.edu.ua",
        "",
    ],
    ids=[
        "empty-local",
        "multiple-at",
        "other-domain",
        "subdomain",
        "suffix-trick",
        "domain-prefix-trick",
        "no-at",
        "empty-string",
    ],
)
def test_rejects_other_addresses(email):
    assert is_ukma_email(email) is False
