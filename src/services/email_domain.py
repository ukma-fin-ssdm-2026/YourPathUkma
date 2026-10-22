"""Перевірка домену пошти НаУКМА.

Використання ШІ: функцію розроблено за TDD, структуру циклів запропоновано Claude за описом та lab06.
"""

UKMA_EMAIL_DOMAIN = "ukma.edu.ua"


def is_ukma_email(email: str) -> bool:
    local, _, domain = email.lower().rpartition("@")
    return bool(local) and "@" not in local and domain == UKMA_EMAIL_DOMAIN
