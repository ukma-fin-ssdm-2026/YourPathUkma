"""
Тести валідації: бізнес-правила плану та схема входу через Google.

Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: запуск pytest локально
і в CI; кожне правило має позитивний і негативний тест.
"""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.api.plan_checks import collect_catalog_flag_violations
from src.api.routes.auth import GoogleLoginRequest
from src.api.routes.plans import PlanItem, PlanPayload
from src.services import plan_rules
from src.services.plan_rules import CatalogFlag

VERIFIER = "a" * 43


def _auth_request(**overrides) -> GoogleLoginRequest:
    data = {"code": "abc", "code_verifier": VERIFIER, "redirect_uri": "http://localhost:5173/callback"}
    data.update(overrides)
    return GoogleLoginRequest(**data)


# --- Дублікати дисциплін ---


def test_check_duplicate_courses_fails_on_duplicates():
    violations = plan_rules.check_duplicate_courses([101, 102, 101])
    assert [v.code for v in violations] == ["DUPLICATE_COURSE"]


def test_check_duplicate_courses_passes_unique():
    assert plan_rules.check_duplicate_courses([101, 102, 103]) == []


# --- Лише вільний вибір ---


def test_check_not_only_free_electives_fails_when_all_free():
    violations = plan_rules.check_not_only_free_electives([True, True])
    assert [v.code for v in violations] == ["ONLY_FREE_ELECTIVES"]


def test_check_not_only_free_electives_passes_with_regular_courses():
    assert plan_rules.check_not_only_free_electives([True, False]) == []
    assert plan_rules.check_not_only_free_electives([False, False]) == []


# --- Ліміт вільного вибору в межах плану ---


@pytest.mark.parametrize("free_credits", [25.5, 30.0], ids=["just-over-limit", "well-over-limit"])
def test_check_free_elective_in_plan_exceeded():
    # Arrange
    free_credits = 25.5

    # Act
    violations = plan_rules.check_free_elective_in_plan(free_credits)

    # Assert
    assert [v.code for v in violations] == ["FREE_ELECTIVE_LIMIT_EXCEEDED"]


@pytest.mark.parametrize("free_credits", [25.0, 15.0, 0.0], ids=["at-limit", "below-limit", "none"])
def test_check_free_elective_in_plan_ok():
    # Arrange
    at_limit, below_limit = 25.0, 15.0

    # Act
    at_limit_violations = plan_rules.check_free_elective_in_plan(at_limit)
    below_limit_violations = plan_rules.check_free_elective_in_plan(below_limit)

    # Assert
    assert at_limit_violations == []
    assert below_limit_violations == []


# --- Прапорець вільного вибору ---


def test_free_flag_mismatch_when_course_has_no_directions():
    # Arrange
    flags = [CatalogFlag(0, has_directions=False, is_free_elective=False)]

    # Act
    violations = plan_rules.check_free_elective_flags(flags)

    # Assert
    assert [v.code for v in violations] == ["FREE_ELECTIVE_FLAG_MISMATCH"]
    assert violations[0].field == "items.0.is_free_elective"


@pytest.mark.parametrize(
    "has_directions,is_free_elective",
    [(False, True), (True, False), (True, True)],
    ids=["no-directions-marked-free", "with-directions-not-free", "with-directions-marked-free"],
)
def test_free_flag_ok(has_directions, is_free_elective):
    # Arrange
    flags = [CatalogFlag(0, has_directions=has_directions, is_free_elective=is_free_elective)]

    # Act
    violations = plan_rules.check_free_elective_flags(flags)

    # Assert
    assert violations == []


def test_catalog_flags_collected_from_items_and_courses():
    # Arrange
    items = [
        SimpleNamespace(course_id=205, is_free_elective=False),
        SimpleNamespace(course_id=101, is_free_elective=False),
    ]
    courses = {205: SimpleNamespace(directions=[]), 101: SimpleNamespace(directions=["Data Science"])}

    # Act
    violations = collect_catalog_flag_violations(items, courses)

    # Assert
    assert [v.field for v in violations] == ["items.0.is_free_elective"]


# --- Загальний ліміт вільного вибору з урахуванням минулих років ---


def test_total_limit_exceeded_with_previous_years():
    violations = plan_rules.check_free_elective_total(current_credits=10.0, used_in_other_years=18.0)
    assert [v.code for v in violations] == ["FREE_ELECTIVE_TOTAL_EXCEEDED"]


def test_total_limit_exactly_25_is_allowed():
    assert plan_rules.check_free_elective_total(10.0, 15.0) == []


def test_total_limit_ignored_without_history():
    assert plan_rules.check_free_elective_total(30.0, 0.0) == []


# --- Конфлікт з нормативними дисциплінами деканату ---


def test_check_deanery_conflicts_detects_conflict():
    courses = [(0, 101), (1, 102)]
    normative_ids = {102, 103}
    violations = plan_rules.check_deanery_conflicts(courses, normative_ids)
    assert [v.code for v in violations] == ["NORMATIVE_CONFLICT"]
    assert violations[0].field == "items.1.course_id"


def test_check_deanery_conflicts_no_conflict():
    courses = [(0, 101), (1, 102)]
    normative_ids = {103, 104}
    assert plan_rules.check_deanery_conflicts(courses, normative_ids) == []


# --- Навантаження на 4 курсі ---


def test_load_levels_forbidden_on_fourth_course():
    assert [v.code for v in plan_rules.check_load_levels(4, load_levels_sent=True)] == ["LOAD_LEVELS_NOT_ALLOWED"]


@pytest.mark.parametrize("course_year,sent", [(4, False), (2, True), (3, True), (2, False)])
def test_load_levels_allowed_otherwise(course_year, sent):
    assert plan_rules.check_load_levels(course_year, sent) == []


def test_payload_tracks_whether_load_levels_were_sent():
    item = PlanItem(course_id=101, title="Функціональне програмування", trimester=1, credits=5.0)
    without = PlanPayload(academic_year=2026, course=4, items=[item])
    with_levels = PlanPayload(academic_year=2026, course=4, items=[item], load_levels={"autumn": "low"})
    assert "load_levels" not in without.model_fields_set
    assert "load_levels" in with_levels.model_fields_set


# --- Авторизація ---


def test_auth_accepts_valid_request():
    assert _auth_request().code_verifier == VERIFIER


@pytest.mark.parametrize("verifier", ["a" * 42, "a" * 129, "a" * 42 + " ", "a" * 42 + "!"])
def test_auth_rejects_bad_code_verifier(verifier):
    with pytest.raises(ValidationError):
        _auth_request(code_verifier=verifier)


@pytest.mark.parametrize("uri", ["javascript:alert(1)", "ftp://example.com/cb", "http://x.com/cb#frag", "/relative"])
def test_auth_rejects_bad_redirect_uri(uri):
    with pytest.raises(ValidationError):
        _auth_request(redirect_uri=uri)


def test_auth_enforces_allowlist_when_configured(monkeypatch):
    monkeypatch.setenv("ALLOWED_REDIRECT_URIS", "https://app.example.com/cb")
    assert _auth_request(redirect_uri="https://app.example.com/cb")
    with pytest.raises(ValidationError):
        _auth_request(redirect_uri="https://evil.example.com/cb")
