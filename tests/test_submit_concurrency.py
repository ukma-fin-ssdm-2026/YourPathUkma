"""
Паралельне подання двох планів одного студента не може обійти ліміт вільного вибору.

Подання серіалізується блокуванням рядка студента (`_lock_student`). Тест потребує справжніх блокувань
рядків, тому виконується лише на PostgreSQL (у CI) і пропускається на SQLite.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: запуск на PostgreSQL 16
(з блокуванням проходить, без нього обидва плани стають submitted і тест падає).
"""

import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from src.api.main import app
from src.api.plan_checks import free_elective_used_in_other_plans
from src.api.routes import plans as plans_routes
from src.db import enums as db_enums
from src.db.config import database_url
from src.db.models import IndividualPlan, PlanItem
from src.db.session import session_factory

pytestmark = pytest.mark.skipif(
    not database_url().startswith("postgresql"),
    reason="Потрібні справжні блокування рядків PostgreSQL (на SQLite FOR UPDATE ігнорується)",
)

STUDENT = 42
YEAR = 2027
PROFESSIONAL_A, PROFESSIONAL_B, FREE_COURSE = 101, 102, 205  # seed: 205 без напрямків, 3 кредити


def _create_plan(professional_id: int) -> int:
    with session_factory()() as db:
        plan = IndividualPlan(
            student_id=STUDENT, academic_year=YEAR, course_year=3, status=db_enums.PlanStatus.DRAFT, total_credits=0
        )
        plan.items = [
            PlanItem(
                course_id=professional_id,
                trimester=db_enums.Trimester.AUTUMN,
                category=db_enums.PlanItemCategory.PROFESSIONAL,
            ),
            PlanItem(
                course_id=FREE_COURSE,
                trimester=db_enums.Trimester.SPRING,
                category=db_enums.PlanItemCategory.FREE_CHOICE,
            ),
        ]
        db.add(plan)
        db.commit()
        return plan.id


@pytest.fixture
def two_draft_plans():
    first, second = _create_plan(PROFESSIONAL_A), _create_plan(PROFESSIONAL_B)
    yield first, second
    with session_factory()() as db:
        db.execute(delete(IndividualPlan).where(IndividualPlan.id.in_([first, second])))
        db.commit()


def test_parallel_submissions_cannot_exceed_the_free_elective_limit(two_draft_plans, monkeypatch):
    first, second = two_draft_plans
    with session_factory()() as db:
        baseline = free_elective_used_in_other_plans(db, STUDENT)
    # Кожен план окремо вміщується (3 кредити вільного вибору), а разом вони б перевищили ліміт
    monkeypatch.setattr("src.services.plan_rules.FREE_ELECTIVE_LIMIT", baseline + 3.5)

    # Змушуємо обидва запити дійти до кінця перевірки «одночасно». З блокуванням другий запит чекає на замок і
    # до бар'єра не доходить, тому бар'єр спрацьовує по тайм-ауту.
    barrier = threading.Barrier(2)
    original_check = plans_routes.enforce_submit_rules

    def check_then_meet(*args, **kwargs):
        original_check(*args, **kwargs)
        try:
            barrier.wait(timeout=2)
        except threading.BrokenBarrierError:
            pass

    monkeypatch.setattr(plans_routes, "enforce_submit_rules", check_then_meet)

    results = {}

    def submit(plan_id: int) -> None:
        results[plan_id] = TestClient(app).post(f"/api/v1/plans/{plan_id}/submit").status_code

    threads = [threading.Thread(target=submit, args=(plan_id,)) for plan_id in (first, second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(results.values()) == [200, 422], results
    with session_factory()() as db:
        statuses = [db.scalar(select(IndividualPlan.status).where(IndividualPlan.id == pid)) for pid in (first, second)]
    assert sorted(status.value for status in statuses) == ["draft", "submitted"]
