"""
Ліміт вільного вибору діє за ВСІ роки разом: запит враховує кредити в усіх поданих планах студента,
зокрема й планах того самого навчального року (раніше їх пропускав, і два подані плани на один рік
могли мати по 25 кредитів).

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest, ruff check
(тест на план того самого року спершу падав на коді з `academic_year !=`).
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select

from src.api.common import ApiError
from src.api.plan_checks import enforce_plan_rules, free_elective_used_in_other_plans
from src.db import enums as db_enums
from src.db.models import Course, IndividualPlan, PlanItem
from src.db.session import session_factory

STUDENT = 42
OTHER_STUDENT = 7
YEAR = 2027
Status = db_enums.PlanStatus


@pytest.fixture
def courses():
    """Кілька дисциплін із seed разом з їхніми кредитами."""
    with session_factory()() as db:
        rows = db.execute(select(Course.id, Course.credits).order_by(Course.id).limit(3)).all()
    assert len(rows) == 3, "У seed замало дисциплін"
    return rows


@pytest.fixture
def plans():
    """Створює плани напряму в БД і видаляє їх після тесту."""
    created = []

    def add(student_id, year, status, course_ids, category=db_enums.PlanItemCategory.FREE_CHOICE):
        with session_factory()() as db:
            plan = IndividualPlan(student_id=student_id, academic_year=year, course_year=3, status=status)
            plan.items = [
                PlanItem(course_id=cid, trimester=db_enums.Trimester.AUTUMN, category=category) for cid in course_ids
            ]
            db.add(plan)
            db.commit()
            created.append(plan.id)
            return plan.id

    yield add

    with session_factory()() as db:
        db.execute(delete(IndividualPlan).where(IndividualPlan.id.in_(created)))
        db.commit()


def used(student_id=STUDENT, exclude=None) -> float:
    with session_factory()() as db:
        return free_elective_used_in_other_plans(db, student_id, exclude)


@pytest.fixture
def baseline() -> float:
    """У seed у студента вже є подані плани з вільним вибором; тести порівнюють зміну відносно них."""
    return used()


def test_submitted_plan_of_the_same_year_is_counted(plans, courses, baseline):
    plans(STUDENT, YEAR, Status.SUBMITTED, [courses[0].id])
    assert used() == pytest.approx(baseline + courses[0].credits)


def test_submitted_plan_of_another_year_is_counted(plans, courses, baseline):
    plans(STUDENT, YEAR + 1, Status.APPROVED, [courses[0].id])
    assert used() == pytest.approx(baseline + courses[0].credits)


def test_plans_of_all_years_are_summed(plans, courses, baseline):
    plans(STUDENT, YEAR, Status.SUBMITTED, [courses[0].id])
    plans(STUDENT, YEAR, Status.AWAITING_DEANERY, [courses[1].id])
    plans(STUDENT, YEAR + 1, Status.APPROVED, [courses[2].id])
    assert used() == pytest.approx(baseline + sum(course.credits for course in courses))


def test_drafts_are_not_counted(plans, courses, baseline):
    plans(STUDENT, YEAR, Status.DRAFT, [courses[0].id])
    assert used() == pytest.approx(baseline)


def test_the_plan_being_checked_is_excluded(plans, courses, baseline):
    own = plans(STUDENT, YEAR, Status.SUBMITTED, [courses[0].id])
    other = plans(STUDENT, YEAR, Status.SUBMITTED, [courses[1].id])
    assert used(exclude=own) == pytest.approx(baseline + courses[1].credits)
    assert used(exclude=other) == pytest.approx(baseline + courses[0].credits)


def test_other_students_plans_are_not_counted(plans, courses, baseline):
    plans(OTHER_STUDENT, YEAR, Status.SUBMITTED, [courses[0].id])
    assert used() == pytest.approx(baseline)


def test_professional_items_are_not_free_electives(plans, courses, baseline):
    plans(STUDENT, YEAR, Status.SUBMITTED, [courses[0].id], category=db_enums.PlanItemCategory.PROFESSIONAL)
    assert used() == pytest.approx(baseline)


def test_new_plan_of_the_same_year_hits_the_total_limit(plans, courses, baseline, monkeypatch):
    """Наскрізно: кредити поданого плану того самого року зменшують місце для нового плану."""
    plans(STUDENT, YEAR, Status.SUBMITTED, [courses[0].id])
    already_used = baseline + float(courses[0].credits)
    # Ліміт на 1 кредит більший за вже використане, а новий план просить 2
    monkeypatch.setattr("src.services.plan_rules.FREE_ELECTIVE_LIMIT", already_used + 1.0)

    item = SimpleNamespace(course_id=courses[1].id, credits=2.0, is_free_elective=True, trimester=1)
    payload = SimpleNamespace(academic_year=YEAR, course=3, items=[item], model_fields_set=set())
    with session_factory()() as db, pytest.raises(ApiError) as caught:
        enforce_plan_rules(db, STUDENT, payload, {courses[1].id: db.get(Course, courses[1].id)})
    assert any(detail.message.startswith("FREE_ELECTIVE_TOTAL_EXCEEDED") for detail in caught.value.details)
