"""Перевірка домену пошти НаУКМА.

Використання ШІ: функцію розроблено за TDD, структуру циклів запропоновано Claude за описом та lab06.
"""


def is_ukma_email(email: str) -> bool:
    local, _, domain = email.lower().rpartition("@")
    return bool(local) and "@" not in local and domain == "ukma.edu.ua"
