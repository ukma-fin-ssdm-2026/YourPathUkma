"""
Тести порівняння знімка САЗ з каталогом: ADD/UPDATE/REMOVE, неповний обхід, поріг, дублікати.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest.
"""

from src.db.enums import ModerationChangeType as T
from src.parser.diff import ExistingCourse, build_changes, item_key


def _existing(code, **overrides):
    base = dict(
        id=int(code),
        saz_code=code,
        title="Курс",
        description="",
        credits=4.0,
        trimester=1,
        recommended_year=2,
        kind="elective",
    )
    return ExistingCourse(**{**base, **overrides})


def _payload(code, **overrides):
    base = dict(
        saz_code=code,
        title="Курс",
        description="",
        credits=4.0,
        trimester=1,
        recommended_year=2,
        kind="elective",
        faculty="ФІ",
    )
    return {**base, **overrides}


def test_new_course_is_added():
    result = build_changes({"7": _payload("7")}, [], complete=True)
    assert [(c.change_type, c.saz_code) for c in result.changes] == [(T.ADD, "7")]
    assert result.changes[0].course_id is None


def test_unchanged_course_produces_nothing():
    result = build_changes({"1": _payload("1")}, [_existing("1")], complete=True)
    assert result.changes == []


def test_changed_fields_become_update_with_diff():
    result = build_changes({"1": _payload("1", title="Нова назва", credits=3.5)}, [_existing("1")], complete=True)
    (change,) = result.changes
    assert change.change_type == T.UPDATE
    assert change.course_id == 1
    assert change.diff == {
        "title": {"old": "Курс", "new": "Нова назва"},
        "credits": {"old": 4.0, "new": 3.5},
    }
    assert change.payload["title"] == "Нова назва" and "kind" not in change.payload


def test_credits_compared_numerically():
    result = build_changes({"1": _payload("1", credits=4)}, [_existing("1", credits=4.0)], complete=True)
    assert result.changes == []


def test_missing_courses_removed_only_after_complete_scan():
    existing = [_existing(str(i)) for i in range(1, 11)]
    scanned = {str(i): _payload(str(i)) for i in range(1, 10)}
    partial = build_changes(scanned, existing, complete=False)
    assert partial.changes == []
    full = build_changes(scanned, existing, complete=True)
    assert [(c.change_type, c.saz_code) for c in full.changes] == [(T.REMOVE, "10")]


def test_mass_removal_is_held_back():
    existing = [_existing(str(i)) for i in range(1, 11)]
    result = build_changes({"1": _payload("1")}, existing, complete=True)
    assert result.changes == []
    assert result.held_removals == 9


def test_manual_and_archived_courses_are_not_removed():
    existing = [_existing("1"), _existing("2", synced=False), _existing("3", published=False)]
    result = build_changes({"1": _payload("1")}, existing, complete=True, remove_threshold=1.0)
    assert result.changes == []


def test_pending_duplicate_is_skipped():
    payload = _payload("7")
    pending = {item_key(T.ADD, "7", payload)}
    result = build_changes({"7": payload}, [], complete=True, pending_keys=pending)
    assert result.changes == []
    assert result.skipped_duplicates == 1


def test_changed_instructors_become_update():
    existing = _existing("1", instructors=("Іваненко І.І.",))
    result = build_changes(
        {"1": _payload("1", instructors=["Іваненко І.І.", "Петренко П.П."])}, [existing], complete=True
    )
    (change,) = result.changes
    assert change.change_type == T.UPDATE
    assert change.diff == {"instructors": {"old": ["Іваненко І.І."], "new": ["Іваненко І.І.", "Петренко П.П."]}}
    assert change.payload["instructors"] == ["Іваненко І.І.", "Петренко П.П."]


def test_same_instructors_in_other_case_and_order_are_equal():
    existing = _existing("1", instructors=("Іваненко І.І.", "Петренко П.П."))
    payload = _payload("1", instructors=["ПЕТРЕНКО П.П.", "іваненко і.і."])
    assert build_changes({"1": payload}, [existing], complete=True).changes == []
