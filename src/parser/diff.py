"""
Порівняння знімка САЗ з каталогом `courses`: що додати, змінити, архівувати. Чиста логіка без БД.

Правила (ADR-002, spec rule 6 rate-ukma):
- ADD / UPDATE створюються завжди, REMOVE лише після повного обходу (`complete=True`): часткове сканування
  не означає, що курси зникли;
- якщо до архівації кандидатів більше за `remove_threshold` від каталогу, REMOVE не створюються взагалі
  (імовірно, змінилась розмітка або фільтр), про це повідомляється в `held_removals`;
- вже очікуваний у черзі елемент із тим самим вмістом не дублюється.

Обмеження: `courses` не зберігає навчальний рік, тому кандидатами на REMOVE вважаються опубліковані курси,
які раніше вже створені синхронізацією (`synced=True`). Курси, додані вручну, не архівуються.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: tests/test_saz_diff.py.
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from ..db import enums as db_enums

REMOVE_THRESHOLD = 0.2
_COMPARED = ("title", "description", "credits", "trimester", "recommended_year", "kind", "instructors")


@dataclass(frozen=True)
class ExistingCourse:
    id: int
    saz_code: str
    title: str
    description: str
    credits: float
    trimester: int
    recommended_year: int
    kind: str
    published: bool = True
    synced: bool = True  # курс створений синхронізацією (`last_sync_job_id` не порожній)
    instructors: Tuple[str, ...] = ()


@dataclass
class Change:
    change_type: db_enums.ModerationChangeType
    saz_code: str
    course_id: Optional[int]
    payload: Dict[str, Any]
    diff: Optional[Dict[str, Any]] = None


@dataclass
class DiffResult:
    changes: List[Change] = field(default_factory=list)
    held_removals: int = 0  # скільки REMOVE не створено через поріг
    skipped_duplicates: int = 0

    def count(self, change_type: db_enums.ModerationChangeType) -> int:
        return sum(1 for c in self.changes if c.change_type == change_type)


def item_key(
    change_type: db_enums.ModerationChangeType, saz_code: str, payload: Dict[str, Any]
) -> Tuple[str, str, str]:
    """Ключ для відсікання дублікатів `pending`: тип, код курсу і хеш вмісту."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return change_type.value, saz_code, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _same(field_name: str, old: Any, new: Any) -> bool:
    if field_name == "credits":
        return round(float(old), 2) == round(float(new), 2)
    if field_name == "instructors":
        return sorted(n.casefold() for n in old) == sorted(n.casefold() for n in new)
    return old == new


def _plain(value: Any) -> Any:
    return list(value) if isinstance(value, tuple) else value


def build_changes(
    scanned: Dict[str, Dict[str, Any]],
    existing: Iterable[ExistingCourse],
    *,
    complete: bool,
    pending_keys: Optional[Set[Tuple[str, str, str]]] = None,
    remove_threshold: float = REMOVE_THRESHOLD,
) -> DiffResult:
    pending = pending_keys or set()
    by_code = {c.saz_code: c for c in existing}
    result = DiffResult()

    def push(change: Change) -> None:
        if item_key(change.change_type, change.saz_code, change.payload) in pending:
            result.skipped_duplicates += 1
        else:
            result.changes.append(change)

    for code, payload in scanned.items():
        course = by_code.get(code)
        if course is None:
            push(Change(db_enums.ModerationChangeType.ADD, code, None, payload))
            continue
        diff = {
            name: {"old": _plain(getattr(course, name)), "new": payload[name]}
            for name in _COMPARED
            if name in payload and not _same(name, getattr(course, name), payload[name])
        }
        if diff:
            update = {name: change["new"] for name, change in diff.items()}
            extras = {k: v for k, v in payload.items() if k not in _COMPARED}
            push(Change(db_enums.ModerationChangeType.UPDATE, code, course.id, {**extras, **update}, diff))

    if complete:
        candidates = [c for c in by_code.values() if c.published and c.synced and c.saz_code not in scanned]
        catalog_size = max(len([c for c in by_code.values() if c.published]), 1)
        if len(candidates) > remove_threshold * catalog_size:
            result.held_removals = len(candidates)
        else:
            for course in candidates:
                push(
                    Change(
                        db_enums.ModerationChangeType.REMOVE, course.saz_code, course.id, {"saz_code": course.saz_code}
                    )
                )
    return result
