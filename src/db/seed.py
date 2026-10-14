"""
Демо-дані для розробки і тестів: ті самі дисципліни, викладачі, напрямки і плани, що були в заглушках API.

Ідентифікатори фіксовані, бо на них покладаються фронтенд і тести (contract.md §5): студент 42 (його повертає
заглушка автентифікації), плани 1 (draft) і 2 (submitted) — його, план 3 — іншого студента.

Запуск: `python -m src.db.seed` (лише якщо в БД ще немає користувачів).

Використання ШІ: файл створено за допомогою Claude (Claude Code) з даних колишніх заглушок
src/api/routes/{disciplines,reference,plans}.py. Перевірка: pytest на SQLite і PostgreSQL.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .base import normalize_text
from .enums import (
    CourseKind,
    CourseYearSource,
    PlanItemCategory,
    PlanStatus,
    Trimester,
    UserRole,
)
from .models import (
    Course,
    CourseDirection,
    CourseInstructor,
    Direction,
    IndividualPlan,
    Instructor,
    PlanItem,
    StudentProfile,
    User,
)
from .session import session_factory

_DIRECTIONS = [
    (1, "Data Science", "Аналіз даних і машинне навчання"),
    (2, "Cybersecurity", None),
    (3, "Software Engineering", "Проєктування та розробка програмних систем"),
]

_INSTRUCTORS = [(7, "Петренко І. М."), (8, "Коваленко О. В."), (9, "Мельник Т. С."), (10, "Шевченко А. П.")]

# id, назва, опис, тип, викладач, рік, триместр, кредити, напрямки
_COURSES = [
    (101, "Функціональне програмування", "Основи функціональної парадигми.", CourseKind.ELECTIVE, 7, 2, 1, 5.0, [3, 1]),
    (102, "Основи кібербезпеки", "Базові принципи захисту інформації.", CourseKind.ELECTIVE, 8, 3, 2, 4.0, [2]),
    (205, "Управління цифровим продуктом", "Життєвий цикл цифрового продукту.", CourseKind.ELECTIVE, 9, 2, 2, 3.0, []),
    (
        301,
        "Алгоритми та структури даних",
        "Нормативна дисципліна від деканату.",
        CourseKind.NORMATIVE,
        10,
        2,
        1,
        6.0,
        [],
    ),
]

# id, email, ПІБ, роль, курс
_USERS = [
    (1, "admin@ukma.edu.ua", "Адміністратор", UserRole.ADMIN, None),
    (7, "other.student@ukma.edu.ua", "Інший Студент", UserRole.STUDENT, 3),
    (42, "student@ukma.edu.ua", "Тестовий Студент", UserRole.STUDENT, 2),
]

# id, власник, статус
_PLANS = [(1, 42, PlanStatus.DRAFT), (2, 42, PlanStatus.SUBMITTED), (3, 7, PlanStatus.DRAFT)]

_TABLES_WITH_FIXED_IDS = ["directions", "instructors", "courses", "users", "individual_plans", "plan_items"]


def seed_demo_data(db: Session) -> bool:
    """Додає демо-дані в порожню БД. Повертає False, якщо дані вже є."""
    if db.scalar(select(func.count()).select_from(User)):
        return False

    for direction_id, name, description in _DIRECTIONS:
        db.add(Direction(id=direction_id, name=name, name_normalized=normalize_text(name), description=description))
    for instructor_id, full_name in _INSTRUCTORS:
        db.add(Instructor(id=instructor_id, full_name=full_name, full_name_normalized=normalize_text(full_name)))
    db.flush()

    for course_id, title, description, kind, instructor_id, year, trimester, credits, direction_ids in _COURSES:
        db.add(
            Course(
                id=course_id,
                saz_code=f"SAZ-{course_id}",
                title=title,
                title_normalized=normalize_text(title),
                description=description,
                credits=credits,
                trimester=Trimester.from_number(trimester),
                recommended_year=year,
                kind=kind,
                course_instructors=[CourseInstructor(instructor_id=instructor_id)],
            )
        )
        for direction_id in direction_ids:
            db.add(CourseDirection(course_id=course_id, direction_id=direction_id))

    for user_id, email, full_name, role, course_year in _USERS:
        user = User(id=user_id, google_sub=f"seed-{user_id}", email=email, full_name=full_name, role=role)
        if role == UserRole.STUDENT:
            user.student_profile = StudentProfile(
                specialty="Інженерія програмного забезпечення",
                course_year=course_year,
                course_year_source=CourseYearSource.SELF_DECLARED,
            )
        db.add(user)
    db.flush()

    for plan_id, owner_id, status in _PLANS:
        db.add(
            IndividualPlan(
                id=plan_id,
                student_id=owner_id,
                academic_year=2026,
                course_year=2,
                status=status,
                total_credits=8.0,
                created_at=datetime(2026, 9, plan_id, 10, 0, tzinfo=timezone.utc),
                items=[
                    PlanItem(
                        id=plan_id * 10 + 1,
                        course_id=101,
                        trimester=Trimester.AUTUMN,
                        category=PlanItemCategory.PROFESSIONAL,
                    ),
                    PlanItem(
                        id=plan_id * 10 + 2,
                        course_id=205,
                        trimester=Trimester.SPRING,
                        category=PlanItemCategory.FREE_CHOICE,
                    ),
                ],
            )
        )
    db.flush()
    _reset_identity_sequences(db)
    return True


def _reset_identity_sequences(db: Session) -> None:
    """Після вставки з явними id PostgreSQL-лічильник identity треба зсунути, інакше наступний INSERT дасть конфлікт."""
    if db.get_bind().dialect.name != "postgresql":
        return
    for table in _TABLES_WITH_FIXED_IDS:
        db.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), (SELECT MAX(id) FROM {table}))"))


def main() -> None:
    with session_factory()() as db:
        if seed_demo_data(db):
            db.commit()
            print("Демо-дані додано.")
        else:
            print("У БД уже є користувачі, демо-дані не додавались.")


if __name__ == "__main__":
    main()
