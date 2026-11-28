"""Використання ШІ: Codex додав регресії #291; перевірка: pytest."""

from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup

from src.db import enums
from src.db.models.catalog import Course
from src.db.models.deanery import DeaneryPlanDocument, NormativeCourseEntry
from src.db.models.history import AcademicRecord
from src.db.session import session_factory
from src.parser.parsers.card import _semesters
from src.services.plan_workload import evaluate_plan_workload


@pytest.mark.parametrize(
    "label, expected", [("4 год./тижд.", 4), ("2,5 год./тижд.", 2.5), ("0 год./тижд.", 0), ("26 лекц.", None)]
)
def test_visible_weekly_label(label, expected):
    cell = BeautifulSoup(f'<td><span title="26 годин на тиждень">{label}</span></td>', "html.parser").td
    assert _semesters(cell, {"Весна": cell})[0].weekly_hours == expected


def test_semesters_keep_separate_hours():
    soup = BeautifulSoup("<table><td>3 кред. 2 год./тижд.</td><td>4 кред. 4 год./тижд.</td></table>", "html.parser")
    a, b = soup.find_all("td")
    assert [s.weekly_hours for s in _semesters(soup, {"Осінь": a, "Весна": b})] == [2, 4]


@pytest.fixture
def workload_db():
    with session_factory()() as db:
        yield db
        db.rollback()


def course(db, code, credits=5, hours=4):
    c = Course(
        saz_code=code,
        title=code,
        title_normalized=code,
        credits=credits,
        trimester=enums.Trimester.AUTUMN,
        recommended_year=3,
        kind=enums.CourseKind.ELECTIVE,
        semesters=[{"number": 5, "season": "Осінь", "credits": credits, "weekly_hours": hours}],
    )
    db.add(c)
    db.flush()
    return c


def document(db, entries=()):
    doc = DeaneryPlanDocument(
        student_id=42,
        academic_year=2029,
        content=b"x",
        size_bytes=1,
        original_filename="test.pdf",
        mime_type=enums.DocumentMimeType.PDF,
        sha256="a" * 64,
        parse_status=enums.DocumentParseStatus.PARSED,
    )
    doc.normative_courses = [
        NormativeCourseEntry(course_id=c.id, raw_title=c.title, credits=cr, trimester=enums.Trimester.AUTUMN)
        for c, cr in entries
    ]
    db.add(doc)
    db.flush()
    return doc


def item(c):
    return SimpleNamespace(course_id=c.id, title=c.title, trimester=1, credits=float(c.credits))


@pytest.mark.parametrize(
    "hours,level,exceeded",
    [
        (19.9, "low", False),
        (20, "medium", False),
        (22.9, "medium", False),
        (23, "high", False),
        (25, "high", False),
        (25.1, None, True),
    ],
)
def test_weekly_boundaries_include_normative(workload_db, hours, level, exceeded):
    db = workload_db
    elective = course(db, "weekly", hours=hours - 4)
    norm = course(db, "normative", hours=4)
    document(db, [(norm, 52)])
    result = evaluate_plan_workload(db, 42, 2029, [item(elective)])
    assert result.workload_by_trimester["1"]["known_weekly_hours"] == hours
    assert result.workload_by_trimester["1"]["level"] == level
    assert bool(result.errors) == exceeded


@pytest.mark.parametrize("total,warn", [(56.9, True), (57, False), (60, False), (65, False)])
def test_annual_minimum_not_maximum(workload_db, total, warn):
    db = workload_db
    c = course(db, "annual")
    n = course(db, "norm")
    document(db, [(n, total - 5)])
    result = evaluate_plan_workload(db, 42, 2029, [item(c)], {"autumn": "low"})
    assert result.year_total_credits == total
    codes = {v.code for v in result.warnings}
    assert ("YEAR_CREDITS_BELOW_MIN" in codes) == warn
    assert ("LOW_LOAD_FUTURE_INCREASE" in codes) != warn


def test_latest_document_history_dedup_and_isolation(workload_db):
    db = workload_db
    c, n = course(db, "selected"), course(db, "norm")
    old = document(db, [(n, 100)])
    doc = document(db, [(n, 20)])
    for cid, amount, docid in [(c.id, 5, None), (n.id, 20, doc.id), (None, 100, old.id), (None, 10, None)]:
        db.add(
            AcademicRecord(
                student_id=42,
                academic_year=2029,
                course_year=3,
                course_id=cid,
                title="History",
                credits=amount,
                trimester=enums.Trimester.AUTUMN,
                category=enums.AcademicCategory.PROFESSIONAL,
                source=enums.RecordSource.SELF_DECLARED,
                document_id=docid,
            )
        )
    db.flush()
    result = evaluate_plan_workload(db, 42, 2029, [item(c)])
    assert result.year_total_credits == 35
    assert result.workload_by_trimester["1"]["known_weekly_hours"] == 8
    assert not result.complete
    assert len(result.workload_by_trimester["1"]["missing_courses"]) == 1


def test_unknown_and_zero_are_distinct(workload_db):
    db = workload_db
    c = course(db, "zero", hours=0)
    document(db)
    assert evaluate_plan_workload(db, 42, 2029, [item(c)]).complete
    c.semesters = []
    db.flush()
    result = evaluate_plan_workload(db, 42, 2029, [item(c)])
    assert not result.complete
    assert result.workload_by_trimester["1"]["level"] is None


def test_old_bundles_allow_missing_weekly_hours():
    from src.parser.bundle import SemesterFields

    assert SemesterFields(number=1, season="Осінь", credits=5).weekly_hours is None
    with pytest.raises(ValueError):
        SemesterFields(number=1, season="Осінь", credits=5, weekly_hours=float("nan"))


def test_linked_and_unlinked_history_deduplicate(workload_db):
    db = workload_db
    c = course(db, "Algorithms", hours=4)
    document(db)
    db.add(
        AcademicRecord(
            student_id=42,
            academic_year=2029,
            course_year=3,
            course_id=None,
            title="  ALGORITHMS ",
            credits=5,
            trimester=enums.Trimester.AUTUMN,
            category=enums.AcademicCategory.PROFESSIONAL,
            source=enums.RecordSource.SELF_DECLARED,
        )
    )
    db.flush()
    result = evaluate_plan_workload(db, 42, 2029, [item(c)])
    assert result.year_total_credits == 5
    assert result.complete
