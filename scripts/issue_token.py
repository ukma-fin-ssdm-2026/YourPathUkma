import sys

from sqlalchemy import select

from src.api.tokens import issue_access_token
from src.db.models.users import User
from src.db.session import session_factory


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
