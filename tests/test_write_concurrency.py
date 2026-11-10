"""Гонки між перевіркою й записом у планах та академічній історії.

Використання ШІ: Codex додав регресійні тести. Перевірка: pytest на PostgreSQL до й після виправлення.
"""

from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event
from time import monotonic

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select, text

from src.api.common import get_current_student_id
from src.api.main import app
from src.db.config import database_url
from src.db.enums import PlanStatus
from src.db.models import AcademicRecord, IndividualPlan, User
from src.db.models.users import StudentProfile
from src.db.session import get_engine, session_factory

pytestmark = pytest.mark.skipif(
    not database_url().startswith("postgresql"),
    reason="Потрібні блокування рядків і pg_blocking_pids у PostgreSQL",
)

WAIT_SECONDS = 15
PLAN_URL = "/api/v1/plans"
HISTORY_URL = "/api/v1/me/academic-history"
PLAN = {
    "academic_year": 2027,
    "course": 3,
    "items": [{"course_id": 101, "title": "Функціональне програмування", "trimester": 1, "credits": 5}],
}


def _concurrent_requests(first_request, second_request, pause_commit):
    """Затримує перший commit, доки другий запит завершиться або чекатиме на його транзакцію."""
    ready = Queue()
    release = Event()
    factory = session_factory()

    def before_commit(db):
        if pause_commit(db):
            ready.put(db.scalar(text("SELECT pg_backend_pid()")))
            assert release.wait(WAIT_SECONDS * 2), "Не отримано сигналу для завершення транзакції"

    event.listen(factory, "before_commit", before_commit)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(first_request)
            try:
                first_pid = ready.get(timeout=WAIT_SECONDS)
                second = executor.submit(second_request)
                deadline = monotonic() + WAIT_SECONDS
                with get_engine().connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
                    while not second.done():
                        if observer.scalar(
                            text(
                                "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                                "WHERE :pid = ANY(pg_blocking_pids(pid)))"
                            ),
                            {"pid": first_pid},
                        ):
                            break
                        assert monotonic() < deadline, "Другий запит не завершився й не очікує на перший"
                        release.wait(0.02)
            finally:
                release.set()
            return first.result(timeout=WAIT_SECONDS), second.result(timeout=WAIT_SECONDS)
    finally:
        event.remove(factory, "before_commit", before_commit)


@pytest.fixture
def draft_plan():
    response = TestClient(app).post(PLAN_URL, json=PLAN)
    assert response.status_code == 201, response.text
    plan_id = response.json()["id"]
    yield plan_id
    with session_factory()() as db:
        db.execute(delete(IndividualPlan).where(IndividualPlan.id == plan_id))
        db.commit()


@pytest.mark.parametrize("method, error_code", [("PUT", "PLAN_NOT_EDITABLE"), ("DELETE", "PLAN_NOT_DELETABLE")])
def test_submitting_plan_rejects_concurrent_draft_mutation(draft_plan, method, error_code):
    url = f"{PLAN_URL}/{draft_plan}"
    changed_plan = {
        **PLAN,
        "items": [{"course_id": 102, "title": "Основи кібербезпеки", "trimester": 2, "credits": 4}],
    }

    def is_submission(db):
        return any(
            isinstance(row, IndividualPlan) and row.id == draft_plan and row.status == PlanStatus.SUBMITTED
            for row in db.dirty
        )

    submitted, mutation = _concurrent_requests(
        lambda: TestClient(app, raise_server_exceptions=False).post(f"{url}/submit"),
        lambda: TestClient(app).request(method, url, **({"json": changed_plan} if method == "PUT" else {})),
        is_submission,
    )

    assert mutation.status_code == 409, mutation.text
    assert mutation.json()["code"] == error_code
    assert submitted.status_code == 200, submitted.text
    with session_factory()() as db:
        plan = db.get(IndividualPlan, draft_plan)
        assert plan.status == PlanStatus.SUBMITTED
        assert [item.course_id for item in plan.items] == [101]


@pytest.fixture
def history_student(monkeypatch):
    with session_factory()() as db:
        user = User(ms_oid="race-history", email="race-history@example.test", full_name="Студент")
        user.student_profile = StudentProfile(course_year=3, specialty="Комп'ютерні науки")
        db.add(user)
        db.commit()
        student_id = user.id
    monkeypatch.setitem(app.dependency_overrides, get_current_student_id, lambda: student_id)
    yield student_id
    with session_factory()() as db:
        db.execute(delete(User).where(User.id == student_id))
        db.commit()


@pytest.mark.parametrize(
    "category, prior_credits, error_code",
    [
        ("free_choice", [23], "FREE_ELECTIVE_LIMIT_EXCEEDED"),
        ("professional", [30] * 7 + [28], "TOTAL_CREDITS_EXCEEDED"),
    ],
)
def test_concurrent_history_writes_cannot_exceed_credit_limit(history_student, category, prior_credits, error_code):
    def record(title, credits):
        return {
            "title": title,
            "credits": credits,
            "academic_year": 2025,
            "course_year": 2,
            "trimester": 1,
            "category": category,
        }

    def add_records(records):
        return TestClient(app).post(HISTORY_URL, json={"records": records})

    baseline = add_records(
        [record(f"Попередня дисципліна {index}", credits) for index, credits in enumerate(prior_credits)]
    )
    assert baseline.status_code == 201, baseline.text
    first, second = _concurrent_requests(
        lambda: add_records([record("Паралельна дисципліна А", 2)]),
        lambda: add_records([record("Паралельна дисципліна Б", 2)]),
        lambda db: any(isinstance(row, AcademicRecord) and row.title == "Паралельна дисципліна А" for row in db.new),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 422, second.text
    assert error_code in second.json()["details"][0]["message"]
    with session_factory()() as db:
        credits = db.scalars(select(AcademicRecord.credits).where(AcademicRecord.student_id == history_student)).all()
    assert sum(credits) == sum(prior_credits) + 2
