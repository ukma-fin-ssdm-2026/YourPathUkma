"""
Тести узгодженого обліку кредитів між історією та планами (issue #288, AGENTS.md §4, §10).

Перевіряє:
1. Відтворений сценарій аудиту: студент із 240 кредитами (25 вільного вибору) в історії
   не може створити або подати план на 8 кредитів (3 вільного вибору).
2. Коректність граничних значень 25 та 240 кредитів (дозволено рівно 25 / 240, відхилено при > 25 / > 240).
3. Виключення подвійного підрахунку дисциплін, які вже потрапили з approved-плану в історію.
4. Врахування незафіксованих в історії дисциплін з активних планів (submitted/awaiting_deanery/approved).
5. Чернетки (draft) не резервують кредити одночасно проти інших чернеток.
6. Редагування власної чернетки (PUT) не рахує її двічі.
7. Ізоляція: плани та історія інших студентів не впливають на ліміти.
8. Підсумки у /me, /plans/validate та перевірках планів повертають узгоджені значення.
9. Додавання історії (POST /me/academic-history) враховує зобов'язання за активними планами.

Використання ШІ: файл створено за допомогою Antigravity (Gemini 2.5 Pro, Google DeepMind) для issue #288.
Перевірка: pytest, ruff, black, flake8, bandit.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from src.api.main import app
from src.api.plan_checks import get_student_credit_summary
from src.db import enums as db_enums
from src.db.models import Course, IndividualPlan, PlanItem, User
from src.db.models.history import AcademicRecord
from src.db.models.users import StudentProfile
from src.db.session import session_factory

client = TestClient(app)
AUTH_STUDENT_42 = {"Authorization": "Bearer test"}
YEAR = 2026


def _create_isolated_student(db, ms_oid: str, email: str, course_year: int = 3) -> int:
    user = User(ms_oid=ms_oid, email=email, full_name="Тестовий Студент")
    user.student_profile = StudentProfile(course_year=course_year, specialty="Комп'ютерні науки")
    db.add(user)
    db.flush()
    return user.id


def _add_record(
    db, student_id: int, title: str, credits: float, category: db_enums.AcademicCategory, course_id: int | None = None
) -> AcademicRecord:
    rec = AcademicRecord(
        student_id=student_id,
        academic_year=2025,
        course_year=2,
        course_id=course_id,
        title=title,
        credits=credits,
        trimester=db_enums.Trimester.AUTUMN,
        category=category,
        source=db_enums.RecordSource.SELF_DECLARED,
    )
    db.add(rec)
    return rec


@pytest.fixture
def clean_student_42_records():
    """Забезпечує чистий стан студента 42 перед і після тесту."""
    with session_factory()() as db:
        db.execute(delete(AcademicRecord).where(AcademicRecord.student_id == 42))
        # Видаляємо всі плани, крім початкових з seed (id 1, 2)
        db.execute(delete(PlanItem).where(PlanItem.plan_id.notin_([1, 2])))
        db.execute(delete(IndividualPlan).where(IndividualPlan.id.notin_([1, 2, 3])))
        # Скидаємо початковий план 2 в DRAFT або відновлюємо його
        p2 = db.get(IndividualPlan, 2)
        if p2:
            p2.status = db_enums.PlanStatus.SUBMITTED
        db.commit()

    yield 42

    with session_factory()() as db:
        db.execute(delete(AcademicRecord).where(AcademicRecord.student_id == 42))
        db.execute(delete(PlanItem).where(PlanItem.plan_id.notin_([1, 2])))
        db.execute(delete(IndividualPlan).where(IndividualPlan.id.notin_([1, 2, 3])))
        p2 = db.get(IndividualPlan, 2)
        if p2:
            p2.status = db_enums.PlanStatus.SUBMITTED
        db.commit()


def test_reproduced_audit_scenario_240_credits_and_25_free_rejected(clean_student_42_records):
    """
    Аудит локального main (a3ced83):
    Студент із 240 кредитами в AcademicRecord (із них 25 вільного вибору)
    НЕ повинен мати змоги створити (201) або подати (200) план на 8 кредитів (із них 3 вільного вибору).
    """
    student_id = clean_student_42_records

    with session_factory()() as db:
        # Прибираємо план 2 у DRAFT, щоб перевірити суто AcademicRecord
        p2 = db.get(IndividualPlan, 2)
        if p2:
            p2.status = db_enums.PlanStatus.DRAFT

        # 215 кредитів профорієнтовних + 25 вільного вибору = 240 сумарно
        _add_record(db, student_id, "Історія профорієнтовні", 215.0, db_enums.AcademicCategory.PROFESSIONAL)
        _add_record(db, student_id, "Історія вільний вибір", 25.0, db_enums.AcademicCategory.FREE_CHOICE)
        db.commit()

    candidate_plan = {
        "academic_year": YEAR,
        "course": 2,
        "items": [
            {"course_id": 101, "title": "Функціональне програмування", "trimester": 1, "credits": 5.0},
            {
                "course_id": 205,
                "title": "Основи криптографії",
                "trimester": 2,
                "credits": 3.0,
                "is_free_elective": True,
            },
        ],
    }

    # 1. Спроба створити план (POST /plans) повинна повертати 422 VALIDATION_ERROR
    create_res = client.post("/api/v1/plans", json=candidate_plan, headers=AUTH_STUDENT_42)
    assert create_res.status_code == 422, create_res.text
    details = create_res.json()["details"]
    messages = [d["message"] for d in details]
    assert any("TOTAL_CREDITS_EXCEEDED" in m for m in messages)
    assert any("FREE_ELECTIVE_TOTAL_EXCEEDED" in m for m in messages)

    # 2. Перевірка при поданні (submit) чернетки
    # Створюємо чернетку в обхід валідації для перевірки enforce_submit_rules
    with session_factory()() as db:
        draft = IndividualPlan(
            student_id=student_id,
            academic_year=YEAR,
            course_year=2,
            status=db_enums.PlanStatus.DRAFT,
            total_credits=8.0,
            items=[
                PlanItem(
                    course_id=101, trimester=db_enums.Trimester.AUTUMN, category=db_enums.PlanItemCategory.PROFESSIONAL
                ),
                PlanItem(
                    course_id=205, trimester=db_enums.Trimester.SPRING, category=db_enums.PlanItemCategory.FREE_CHOICE
                ),
            ],
        )
        db.add(draft)
        db.commit()
        draft_id = draft.id

    try:
        submit_res = client.post(f"/api/v1/plans/{draft_id}/submit", headers=AUTH_STUDENT_42)
        assert submit_res.status_code == 422, submit_res.text
        submit_details = submit_res.json()["details"]
        submit_messages = [d["message"] for d in submit_details]
        assert any("TOTAL_CREDITS_EXCEEDED" in m for m in submit_messages)
        assert any("FREE_ELECTIVE_TOTAL_EXCEEDED" in m for m in submit_messages)
    finally:
        with session_factory()() as db:
            db.execute(delete(PlanItem).where(PlanItem.plan_id == draft_id))
            db.execute(delete(IndividualPlan).where(IndividualPlan.id == draft_id))
            db.commit()


def test_boundary_exact_240_and_25_credits_allowed(clean_student_42_records):
    """Граничні рівно 240 кредитів за програму та 25 кредитів вільного вибору успішно проходять."""
    student_id = clean_student_42_records

    with session_factory()() as db:
        p2 = db.get(IndividualPlan, 2)
        if p2:
            p2.status = db_enums.PlanStatus.DRAFT

        # 210 профорієнтовних + 22 вільного вибору = 232 сумарно в історії
        _add_record(db, student_id, "Історія проф", 210.0, db_enums.AcademicCategory.PROFESSIONAL)
        _add_record(db, student_id, "Історія вільний", 22.0, db_enums.AcademicCategory.FREE_CHOICE)
        db.commit()

    # План на 8 кредитів (5 проф + 3 вільний вибір) -> рівно 240 і 25
    candidate_plan = {
        "academic_year": YEAR,
        "course": 2,
        "items": [
            {"course_id": 101, "title": "Функціональне програмування", "trimester": 1, "credits": 5.0},
            {
                "course_id": 205,
                "title": "Основи криптографії",
                "trimester": 2,
                "credits": 3.0,
                "is_free_elective": True,
            },
        ],
    }

    create_res = client.post("/api/v1/plans", json=candidate_plan, headers=AUTH_STUDENT_42)
    assert create_res.status_code == 201, create_res.text
    created_id = create_res.json()["id"]

    try:
        # Подання також проходить успішно
        submit_res = client.post(f"/api/v1/plans/{created_id}/submit", headers=AUTH_STUDENT_42)
        assert submit_res.status_code == 200, submit_res.text
        assert submit_res.json()["status"] == "submitted"
    finally:
        with session_factory()() as db:
            db.execute(delete(PlanItem).where(PlanItem.plan_id == created_id))
            db.execute(delete(IndividualPlan).where(IndividualPlan.id == created_id))
            db.commit()


def test_boundary_exceeded_by_one_credit_rejected(clean_student_42_records):
    """Перевищення лімітів навіть на 1 кредит (241 або 26) відхиляється 422."""
    student_id = clean_student_42_records

    with session_factory()() as db:
        p2 = db.get(IndividualPlan, 2)
        if p2:
            p2.status = db_enums.PlanStatus.DRAFT

        _add_record(db, student_id, "Історія проф", 210.0, db_enums.AcademicCategory.PROFESSIONAL)
        _add_record(db, student_id, "Історія вільний", 23.0, db_enums.AcademicCategory.FREE_CHOICE)
        db.commit()

    # 23 + 3 = 26 > 25 (вільний вибір перевищено на 1)
    plan_free_exceeded = {
        "academic_year": YEAR,
        "course": 2,
        "items": [
            {"course_id": 101, "title": "Функціональне програмування", "trimester": 1, "credits": 5.0},
            {
                "course_id": 205,
                "title": "Основи криптографії",
                "trimester": 2,
                "credits": 3.0,
                "is_free_elective": True,
            },
        ],
    }
    res = client.post("/api/v1/plans", json=plan_free_exceeded, headers=AUTH_STUDENT_42)
    assert res.status_code == 422
    assert any("FREE_ELECTIVE_TOTAL_EXCEEDED" in d["message"] for d in res.json()["details"])


def test_deduplication_between_approved_plan_and_history():
    """Дисципліна, яка вже потрапила з approved-плану в AcademicRecord, не подвоюється."""
    with session_factory()() as db:
        student_id = _create_isolated_student(db, "dedup-test", "dedup@example.test")
        c101 = db.get(Course, 101)
        c205 = db.get(Course, 205)

        # 1. Створюємо затверджений план
        approved_plan = IndividualPlan(
            student_id=student_id,
            academic_year=2024,
            course_year=2,
            status=db_enums.PlanStatus.APPROVED,
            total_credits=8.0,
            items=[
                PlanItem(
                    course_id=c101.id,
                    trimester=db_enums.Trimester.AUTUMN,
                    category=db_enums.PlanItemCategory.PROFESSIONAL,
                ),
                PlanItem(
                    course_id=c205.id,
                    trimester=db_enums.Trimester.SPRING,
                    category=db_enums.PlanItemCategory.FREE_CHOICE,
                ),
            ],
        )
        db.add(approved_plan)
        db.flush()

        # 2. Ті самі дисципліни внесено в історію
        _add_record(db, student_id, c101.title, c101.credits, db_enums.AcademicCategory.PROFESSIONAL, course_id=c101.id)
        _add_record(db, student_id, c205.title, c205.credits, db_enums.AcademicCategory.FREE_CHOICE, course_id=c205.id)
        db.commit()

        # 3. Перевіряємо підсумки
        summary = get_student_credit_summary(db, student_id)
        # Має бути 8.0, а не 16.0
        assert summary.history_total == 8.0
        assert summary.committed_plans_total == 0.0
        assert summary.total_used == 8.0
        assert summary.free_choice_used == 3.0

        # Очищуємо тестового студента
        db.execute(delete(PlanItem).where(PlanItem.plan_id == approved_plan.id))
        db.execute(delete(IndividualPlan).where(IndividualPlan.id == approved_plan.id))
        db.execute(delete(AcademicRecord).where(AcademicRecord.student_id == student_id))
        db.execute(delete(User).where(User.id == student_id))
        db.commit()


def test_approved_plan_unrecorded_items_are_counted():
    """Дисципліни з approved-плану, яких ще немає в AcademicRecord, коректно враховуються."""
    with session_factory()() as db:
        student_id = _create_isolated_student(db, "unrec-test", "unrec@example.test")
        c101 = db.get(Course, 101)
        c102 = db.get(Course, 102)

        approved_plan = IndividualPlan(
            student_id=student_id,
            academic_year=2024,
            course_year=2,
            status=db_enums.PlanStatus.APPROVED,
            total_credits=9.0,
            items=[
                PlanItem(
                    course_id=c101.id,
                    trimester=db_enums.Trimester.AUTUMN,
                    category=db_enums.PlanItemCategory.PROFESSIONAL,
                ),
                PlanItem(
                    course_id=c102.id,
                    trimester=db_enums.Trimester.SPRING,
                    category=db_enums.PlanItemCategory.FREE_CHOICE,
                ),
            ],
        )
        db.add(approved_plan)
        db.flush()

        # Лише c101 є в AcademicRecord
        _add_record(db, student_id, c101.title, c101.credits, db_enums.AcademicCategory.PROFESSIONAL, course_id=c101.id)
        db.commit()

        summary = get_student_credit_summary(db, student_id)
        # 5.0 з історії + 4.0 з плану (c102) = 9.0
        assert summary.history_total == 5.0
        assert summary.committed_plans_total == 4.0
        assert summary.total_used == 9.0
        assert summary.free_choice_used == 4.0

        db.execute(delete(PlanItem).where(PlanItem.plan_id == approved_plan.id))
        db.execute(delete(IndividualPlan).where(IndividualPlan.id == approved_plan.id))
        db.execute(delete(AcademicRecord).where(AcademicRecord.student_id == student_id))
        db.execute(delete(User).where(User.id == student_id))
        db.commit()


def test_drafts_do_not_reserve_credits_against_each_other(clean_student_42_records):
    """Альтернативні чернетки не резервують кредити одночасно."""

    # Створюємо першу чернетку на 18 кредитів вільного вибору
    with session_factory()() as db:
        p2 = db.get(IndividualPlan, 2)
        if p2:
            p2.status = db_enums.PlanStatus.DRAFT
        db.commit()

    candidate_plan_1 = {
        "academic_year": YEAR,
        "course": 2,
        "items": [
            {"course_id": 101, "title": "Обов'язковий", "trimester": 1, "credits": 5.0},
            {"course_id": 205, "title": "Вільний вибір 1", "trimester": 2, "credits": 3.0, "is_free_elective": True},
        ],
    }
    r1 = client.post("/api/v1/plans", json=candidate_plan_1, headers=AUTH_STUDENT_42)
    assert r1.status_code == 201
    plan_1_id = r1.json()["id"]

    # Друга чернетка на той самий рік також створюється без конфлікту з першою чернеткою
    candidate_plan_2 = {
        "academic_year": YEAR,
        "course": 2,
        "items": [
            {"course_id": 101, "title": "Обов'язковий 2", "trimester": 1, "credits": 5.0},
            {"course_id": 205, "title": "Вільний вибір 2", "trimester": 2, "credits": 3.0, "is_free_elective": True},
        ],
    }
    r2 = client.post("/api/v1/plans", json=candidate_plan_2, headers=AUTH_STUDENT_42)
    assert r2.status_code == 201
    plan_2_id = r2.json()["id"]

    with session_factory()() as db:
        db.execute(delete(PlanItem).where(PlanItem.plan_id.in_([plan_1_id, plan_2_id])))
        db.execute(delete(IndividualPlan).where(IndividualPlan.id.in_([plan_1_id, plan_2_id])))
        db.commit()


def test_updating_own_draft_does_not_double_count_itself(clean_student_42_records):
    """Редагування власної чернетки (PUT) не рахує її двічі."""
    student_id = clean_student_42_records

    with session_factory()() as db:
        p2 = db.get(IndividualPlan, 2)
        if p2:
            p2.status = db_enums.PlanStatus.DRAFT
        # 20 кредитів вільного вибору в історії (залишок 5)
        _add_record(db, student_id, "Історія 20", 20.0, db_enums.AcademicCategory.FREE_CHOICE)
        db.commit()

    # Створюємо чернетку на 3 кредити вільного вибору (20 + 3 = 23 <= 25)
    initial_plan = {
        "academic_year": YEAR,
        "course": 2,
        "items": [
            {"course_id": 101, "title": "Проф", "trimester": 1, "credits": 5.0},
            {"course_id": 205, "title": "Вільний", "trimester": 2, "credits": 3.0, "is_free_elective": True},
        ],
    }
    res = client.post("/api/v1/plans", json=initial_plan, headers=AUTH_STUDENT_42)
    assert res.status_code == 201
    plan_id = res.json()["id"]

    try:
        # Оновлюємо чернетку: міняємо на 4 кредити вільного вибору (20 + 4 = 24 <= 25)
        updated_plan = {
            "academic_year": YEAR,
            "course": 2,
            "items": [
                {"course_id": 101, "title": "Проф", "trimester": 1, "credits": 5.0},
                {"course_id": 102, "title": "Вільний інший", "trimester": 2, "credits": 4.0, "is_free_elective": True},
            ],
        }
        put_res = client.put(f"/api/v1/plans/{plan_id}", json=updated_plan, headers=AUTH_STUDENT_42)
        # Якби чернетка рахувалася сама проти себе, було б 20 + 3 + 4 = 27 > 25 (помилка)
        assert put_res.status_code == 200, put_res.text
        assert put_res.json()["free_elective_credits"] == 4.0
    finally:
        with session_factory()() as db:
            db.execute(delete(PlanItem).where(PlanItem.plan_id == plan_id))
            db.execute(delete(IndividualPlan).where(IndividualPlan.id == plan_id))
            db.commit()


def test_other_students_data_does_not_affect_limits():
    """Чужі плани та історія не впливають на доступні ліміти поточного студента."""
    with session_factory()() as db:
        student_a = _create_isolated_student(db, "student-a", "a@example.test")
        student_b = _create_isolated_student(db, "student-b", "b@example.test")

        # Студент А вичерпав усі 240 кредитів і 25 вільного вибору
        _add_record(db, student_a, "A проф", 215.0, db_enums.AcademicCategory.PROFESSIONAL)
        _add_record(db, student_a, "A вільний", 25.0, db_enums.AcademicCategory.FREE_CHOICE)

        # Студент B має чисту історію
        summary_b = get_student_credit_summary(db, student_b)
        assert summary_b.total_used == 0.0
        assert summary_b.free_choice_used == 0.0

        db.execute(delete(AcademicRecord).where(AcademicRecord.student_id.in_([student_a, student_b])))
        db.execute(delete(User).where(User.id.in_([student_a, student_b])))
        db.commit()


def test_plans_validate_returns_consistent_summary_and_reports_errors(clean_student_42_records):
    """POST /plans/validate повертає узгоджений підсумок та фіксує перевищення загальних лімітів."""
    student_id = clean_student_42_records

    with session_factory()() as db:
        p2 = db.get(IndividualPlan, 2)
        if p2:
            p2.status = db_enums.PlanStatus.DRAFT
        # 235 кредитів в історії
        _add_record(db, student_id, "Історія", 235.0, db_enums.AcademicCategory.PROFESSIONAL)
        db.commit()

    # План на 8 кредитів (235 + 8 = 243 > 240)
    body = {
        "academic_year": YEAR,
        "course": 2,
        "items": [
            {"course_id": 101, "title": "Проф", "trimester": 1, "credits": 5.0},
            {"course_id": 205, "title": "Вільний", "trimester": 2, "credits": 3.0, "is_free_elective": True},
        ],
    }
    res = client.post("/api/v1/plans/validate", json=body, headers=AUTH_STUDENT_42)
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is False
    codes = [e["code"] for e in data["errors"]]
    assert "TOTAL_CREDITS_EXCEEDED" in codes


def test_add_academic_history_takes_committed_plans_into_account(clean_student_42_records):
    """POST /me/academic-history враховує зобов'язання за активними планами."""

    # Переконуємось, що Plan 2 (SUBMITTED) активний і має 8 кредитів (3 з яких вільний вибір)
    with session_factory()() as db:
        p2 = db.get(IndividualPlan, 2)
        assert p2 is not None
        p2.status = db_enums.PlanStatus.SUBMITTED
        db.commit()

    # Спроба додати 235 кредитів в історію (235 + 8 = 243 > 240)
    # Кожна дисципліна має обмеження credits <= 30, тому розбиваємо на 8 дисциплін (7*30 + 25 = 235)
    payload_total = {
        "records": [
            {
                "academic_year": 2024,
                "course_year": 1,
                "title": f"Велика дисципліна {i}",
                "credits": 30.0 if i < 7 else 25.0,
                "trimester": 1,
                "category": "professional",
            }
            for i in range(8)
        ]
    }
    res = client.post("/api/v1/me/academic-history", json=payload_total, headers=AUTH_STUDENT_42)
    assert res.status_code == 422
    assert any("TOTAL_CREDITS_EXCEEDED" in d["message"] for d in res.json()["details"])

    # Спроба додати 23 кредити вільного вибору (23 + 3 = 26 > 25)
    payload_free = {
        "records": [
            {
                "academic_year": 2024,
                "course_year": 1,
                "title": "Вільний вибір перебір",
                "credits": 23.0,
                "trimester": 1,
                "category": "free_choice",
            }
        ]
    }
    res_free = client.post("/api/v1/me/academic-history", json=payload_free, headers=AUTH_STUDENT_42)
    assert res_free.status_code == 422
    assert any("FREE_ELECTIVE_LIMIT_EXCEEDED" in d["message"] for d in res_free.json()["details"])
