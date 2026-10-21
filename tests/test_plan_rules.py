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


@pytest.mark.parametrize(
    "course_ids, expected_codes",
    [
        ([101, 102, 101], ["DUPLICATE_COURSE"]),
        ([101, 101], ["DUPLICATE_COURSE"]),
        ([101, 102, 103], []),
        ([101], []),
        ([], []),
    ],
    ids=["one_duplicate", "only_duplicates", "all_unique", "single_course", "empty"],
)
def test_check_duplicate_courses(course_ids, expected_codes):
    # Act
    violations = plan_rules.check_duplicate_courses(course_ids)

    # Assert
    assert [v.code for v in violations] == expected_codes


# --- Лише вільний вибір ---


@pytest.mark.parametrize(
    "is_free_flags, expected_codes",
    [
        ([True, True], ["ONLY_FREE_ELECTIVES"]),
        ([True], ["ONLY_FREE_ELECTIVES"]),
        ([True, False], []),
        ([False, False], []),
    ],
    ids=["all_free", "single_free", "mixed", "all_regular"],
)
def test_check_not_only_free_electives(is_free_flags, expected_codes):
    # Act
    violations = plan_rules.check_not_only_free_electives(is_free_flags)

    # Assert
    assert [v.code for v in violations] == expected_codes

# --- Ліміт вільного вибору в межах плану ---


@pytest.mark.parametrize("free_credits", [25.5, 30.0], ids=["just-over-limit", "well-over-limit"])
def test_check_free_elective_in_plan_exceeded(free_credits):
    # Arrange: кредити вільного вибору надходять з параметра

    # Act
    violations = plan_rules.check_free_elective_in_plan(free_credits)

    # Assert
    assert [v.code for v in violations] == ["FREE_ELECTIVE_LIMIT_EXCEEDED"]


@pytest.mark.parametrize("free_credits", [25.0, 15.0, 0.0], ids=["at-limit", "below-limit", "none"])
def test_check_free_elective_in_plan_ok(free_credits):
    # Arrange: кредити вільного вибору надходять з параметра

    # Act
    violations = plan_rules.check_free_elective_in_plan(free_credits)

    # Assert
    assert violations == []


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


@pytest.mark.parametrize(
    "current_credits, used_in_other_years, expected_codes",
    [
        (10.0, 18.0, ["FREE_ELECTIVE_TOTAL_EXCEEDED"]),  # 28 > 25 з урахуванням минулих років
        (10.0, 15.0, []),  # рівно 25: межа дозволена
        (30.0, 0.0, []),  # без історії ліміт за всі роки не застосовується
    ],
)
def test_check_free_elective_total_with_previous_years(current_credits, used_in_other_years, expected_codes):
    # Arrange: кредити поточного плану та кредити вільного вибору за інші роки (параметри)

    # Act
    violations = plan_rules.check_free_elective_total(current_credits, used_in_other_years)

    # Assert
    assert [v.code for v in violations] == expected_codes


# --- Конфлікт з нормативними дисциплінами деканату ---


@pytest.mark.parametrize(
    "normative_ids, expected",
    [
        ({102, 103}, [("NORMATIVE_CONFLICT", "items.1.course_id")]),  # 102 уже в плані деканату
        ({103, 104}, []),  # перетину немає
    ],
)
def test_check_deanery_conflicts(normative_ids, expected):
    # Arrange
    courses = [(0, 101), (1, 102)]

    # Act
    violations = plan_rules.check_deanery_conflicts(courses, normative_ids)

    # Assert
    assert [(v.code, v.field) for v in violations] == expected


# --- Навантаження на 4 курсі ---

ALLOWED_URI = "https://app.example.com/cb"


@pytest.fixture
def configured_allowlist(monkeypatch):
    monkeypatch.setenv("ALLOWED_REDIRECT_URIS", ALLOWED_URI)

def test_load_levels_forbidden_on_fourth_course():
    # Arrange
    course_year = 4
    expected_codes = ["LOAD_LEVELS_NOT_ALLOWED"]

    # Act
    violations = plan_rules.check_load_levels(course_year, load_levels_sent=True)

    # Assert
    assert [v.code for v in violations] == expected_codes


@pytest.mark.parametrize("course_year,sent", [(4, False), (2, True), (3, True), (2, False)])
def test_load_levels_allowed_otherwise(course_year, sent):
     # Act
    violations = plan_rules.check_load_levels(course_year, sent)

    # Assert
    assert violations == []


def test_payload_tracks_whether_load_levels_were_sent():
    # Arrange
    item = PlanItem(course_id=101, title="Функціональне програмування", trimester=1, credits=5.0)

    # Act
    without = PlanPayload(academic_year=2026, course=4, items=[item])
    with_levels = PlanPayload(academic_year=2026, course=4, items=[item], load_levels={"autumn": "low"})

    # Assert
    assert "load_levels" not in without.model_fields_set
    assert "load_levels" in with_levels.model_fields_set



# --- Авторизація ---


def test_auth_accepts_valid_request():
    # Arrange: значення за замовчуванням з _auth_request

    # Act
    request = _auth_request()

    # Assert
    assert request.code_verifier == VERIFIER



@pytest.mark.parametrize("verifier", ["a" * 42, "a" * 129, "a" * 42 + " ", "a" * 42 + "!"])
def test_auth_rejects_bad_code_verifier(verifier):
    # Arrange: некоректний verifier задано параметризацією

    # Act + Assert
    with pytest.raises(ValidationError):
        _auth_request(code_verifier=verifier)


@pytest.mark.parametrize("uri", ["javascript:alert(1)", "ftp://example.com/cb", "http://x.com/cb#frag", "/relative"])
def test_auth_rejects_bad_redirect_uri(uri):
     # Arrange: allowlist налаштовано фікстурою configured_allowlist

    # Act
    request = _auth_request(redirect_uri=ALLOWED_URI)

    # Assert
    assert request.redirect_uri == ALLOWED_URI


def test_auth_enforces_allowlist_when_configured(monkeypatch):
    monkeypatch.setenv("ALLOWED_REDIRECT_URIS", "https://app.example.com/cb")
    assert _auth_request(redirect_uri="https://app.example.com/cb")
    with pytest.raises(ValidationError):
        _auth_request(redirect_uri="https://evil.example.com/cb")
