"""
Видає access-токен для користувача з бази: для Swagger UI (Authorize) і ручних запитів без входу через Microsoft.

Запуск з кореня репозиторію: python -m scripts.issue_token admin@ukma.edu.ua
JWT_SECRET і DATABASE_URL береться з .env так само, як у застосунку.

Використання ШІ: читання .env (load_dotenv) додано за допомогою Claude (Claude Code): без нього скрипт падав
з «HMAC key must not be empty». Перевірка: запуск у чистій теці за кроками README.
"""

import sys

from dotenv import load_dotenv
from sqlalchemy import select

load_dotenv()  # до імпорту налаштувань: get_auth_settings() кешується при першому виклику

from src.api.tokens import issue_access_token  # noqa: E402
from src.db.models.users import User  # noqa: E402
from src.db.session import session_factory  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Використання: python -m scripts.issue_token email@ukma.edu.ua")
    email = sys.argv[1].strip().lower()
    with session_factory()() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            sys.exit(f"Користувача {email} не знайдено")
        print(issue_access_token(user.id, user.role.value))


if __name__ == "__main__":
    main()
