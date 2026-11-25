"""
Сервіс звірки дисциплін сертифікатних програм із каталогом САЗ та розрахунку доступності (FR-013, AGENTS.md §4).

Бізнес-правила:
1. Дисципліни сертифіката звіряються з актуальним опублікованим каталогом САЗ без урахування регістру,
   знаків пунктуації та різновидів написання.
2. Неоднозначні fuzzy-збіги не приймаються автоматично і потребують ручного підтвердження адміном.
3. Якщо хоч однієї дисципліни немає в САЗ або вона не опублікована цього року — сертифікатна програма
   автоматично отримує статус UNAVAILABLE.

Використання ШІ: модуль створено за допомогою Antigravity (Gemini 2.5 Pro).
Перевірка: tests/test_certificates_reconciliation.py, pytest, ruff.
"""

from __future__ import annotations

import logging
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import enums as db_enums
from ..db.base import utcnow
from ..db.models.catalog import CertificateProgram, Course
from ..parser.parsers.certificates import normalize_discipline_title

logger = logging.getLogger(__name__)

FUZZY_MATCH_THRESHOLD = 0.75


def _is_ambiguous_match(query: str, target: str) -> bool:
    """Визначає, чи є назви схожими/перетинаються (з урахуванням відмінків в укр. мові), але не збігаються точно."""
    ratio = SequenceMatcher(None, query, target).ratio()
    if ratio >= FUZZY_MATCH_THRESHOLD:
        return True
    if len(query) >= 6 and len(target) >= 6:
        if query in target or target in query:
            return True

    # Перетин основ слів (stems) для відмінюваних слів української мови
    stems_q = {w[:4] for w in query.split() if len(w) >= 4}
    stems_t = {w[:4] for w in target.split() if len(w) >= 4}
    if stems_q and stems_t:
        overlap = len(stems_q & stems_t)
        # Якщо хоча б 2 спільні корені слів або >= 50% слів збігаються за основою
        if overlap >= 2 or (overlap / min(len(stems_q), len(stems_t)) >= 0.5):
            return True
    return False


def reconcile_certificate_course(db: Session, raw_title: str) -> Tuple[Optional[int], str]:
    """
    Звіряє сиру назву дисципліни з опублікованим каталогом САЗ.
    Повертає:
        (course_id, "matched") — якщо знайдено однозначний збіг після нормалізації.
        (None, "ambiguous") — якщо є схожі дисципліни (fuzzy), які потребують підтвердження адміна.
        (None, "not_found") — дисципліну не знайдено в каталозі цього року.
    """
    normalized_query = normalize_discipline_title(raw_title)
    if not normalized_query:
        return None, "not_found"

    # Отримуємо всі опубліковані курси каталогу
    published_courses = db.scalars(
        select(Course).where(Course.publication_status == db_enums.PublicationStatus.PUBLISHED)
    ).all()

    exact_matches: List[Course] = []
    fuzzy_matches: List[Course] = []

    for course in published_courses:
        course_norm = normalize_discipline_title(course.title)
        if course_norm == normalized_query:
            exact_matches.append(course)
        elif _is_ambiguous_match(normalized_query, course_norm):
            fuzzy_matches.append(course)

    # 1. Однозначний точний збіг
    if len(exact_matches) == 1:
        return exact_matches[0].id, "matched"
    if len(exact_matches) > 1:
        # Кілька курсів з однаковою назвою — неоднозначність для адміна
        return None, "ambiguous"

    # 2. Неоднозначні збіги (fuzzy) — заборонено приймати автоматично
    if fuzzy_matches:
        return None, "ambiguous"

    # 3. Не знайдено
    return None, "not_found"


def recalculate_certificate_programs_availability(db: Session) -> Dict[str, int]:
    """
    Перераховує доступність (AVAILABLE / UNAVAILABLE) для ВСІХ сертифікатних програм.
    Програма доступна лише тоді, коли:
    - вона містить хоча б одну дисципліну;
    - ВСІ дисципліни програми прив'язані до курсів (course_id IS NOT NULL);
    - кожен прив'язаний курс реально існує і має статус PUBLISHED у каталозі.
    """
    programs = db.scalars(select(CertificateProgram)).all()

    available_count = 0
    unavailable_count = 0

    # Кеш опублікованих course_id для швидкої перевірки
    published_course_ids = set(
        db.scalars(select(Course.id).where(Course.publication_status == db_enums.PublicationStatus.PUBLISHED)).all()
    )

    for prog in programs:
        courses = prog.courses
        is_available = True

        if not courses:
            is_available = False
        else:
            for item in courses:
                if item.course_id is None or item.course_id not in published_course_ids:
                    is_available = False
                    break

        new_status = (
            db_enums.CertificateAvailability.AVAILABLE if is_available else db_enums.CertificateAvailability.UNAVAILABLE
        )

        if prog.availability != new_status:
            prog.availability = new_status
            prog.updated_at = utcnow()

        if is_available:
            available_count += 1
        else:
            unavailable_count += 1

    db.flush()
    return {"available": available_count, "unavailable": unavailable_count}
