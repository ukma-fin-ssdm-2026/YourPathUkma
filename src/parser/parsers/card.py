"""
Парсер картки курсу з каталогу САЗ: `div.panel` (`panel-default`, а в курсів, обраних студентом, `panel-info`)
із вкладеним `div.panel-collapse#course-card-{id}`.

Значення шукаємо за текстом заголовків `<th>`, а не за класами чи позицією: так розмітка стійкіша до змін.
Необов'язкові блоки (викладач, анотація, специфікації) можуть бути відсутні.

Використання ШІ: файл створено за допомогою Claude (Claude Code) за фікстурами tests/fixtures/saz.
Перевірка: tests/test_saz_card_parser.py.
"""

import re
from typing import Dict, List, Optional

from bs4 import Tag

from ..models import ParsedCourse, Semester, Specialty
from .utils import clean_text, parse_float, parse_int, split_instructors

_SEASONS = ("Осінь", "Весна", "Літо")
_INTERNAL_ID = re.compile(r"^course-card-(\d+)$")
_CREDITS = re.compile(r"(\d+(?:[.,]\d+)?)\s*кред")
_YEAR = re.compile(r"(\d+)\s*рік")
_HOURS = re.compile(r"(\d+)\s*год\.(?!/)")
_SEMESTER_NO = re.compile(r"Семестр\s+(\d+)")


class CardParseError(ValueError):
    """Картку не вдалося розібрати (немає коду курсу або назви)."""


def internal_id_of(panel: Tag) -> Optional[str]:
    body = panel.select_one("div.panel-collapse")
    match = _INTERNAL_ID.match(str(body.get("id", ""))) if body else None
    return match.group(1) if match else None


def card_title_of(panel: Tag) -> Optional[str]:
    link = panel.select_one(".panel-heading .panel-title")
    return clean_text(link.get_text(" ")) or None if link else None


def _rows(body: Tag) -> Dict[str, Tag]:
    """Перше входження кожного заголовка `<th>` -> відповідна `<td>` того ж рядка."""
    rows: Dict[str, Tag] = {}
    for tr in body.select("tr"):
        th, td = tr.find("th", recursive=False), tr.find("td", recursive=False)
        if th is None or td is None:
            continue
        key = clean_text(th.get_text(" "))
        rows.setdefault(key, td)
    return rows


def _specialties(body: Tag) -> List[Specialty]:
    block = body.select_one("div[id$='--spec']")
    result: List[Specialty] = []
    if block is None:
        return result
    for tr in block.select("tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) >= 2:
            name, kind = clean_text(cells[0].get_text(" ")), clean_text(cells[1].get_text(" "))
            if name:
                result.append(Specialty(name=name, type=kind))
    return result


def _semesters(body: Tag, rows: Dict[str, Tag]) -> List[Semester]:
    numbers: List[int] = []
    header = rows.get("Семестри")
    if header is not None:
        numbers = [int(n) for n in _SEMESTER_NO.findall(clean_text(header.get_text(" ")))]

    found = []  # (пора року, кредити) у порядку на сторінці
    for season in _SEASONS:
        cell = rows.get(season)
        if cell is not None:
            found.append((season, parse_float(_first(_CREDITS, clean_text(cell.get_text(" "))))))
    paired = len(numbers) == len(found)
    return [
        Semester(number=numbers[i] if paired else None, season=season, credits=credits)
        for i, (season, credits) in enumerate(found)
    ]


def _first(pattern: re.Pattern, text: str) -> Optional[str]:
    match = pattern.search(text)
    return match.group(1) if match else None


def parse_card(panel: Tag) -> ParsedCourse:
    body = panel.select_one("div.panel-collapse")
    if body is None:
        raise CardParseError("Немає блоку panel-collapse")
    rows = _rows(body)

    code = clean_text(rows["Код"].get_text(" ")) if "Код" in rows else ""
    if not code:
        raise CardParseError("Немає коду курсу")
    title = card_title_of(panel)
    if not title:
        raise CardParseError(f"Немає назви курсу {code}")

    info = clean_text(rows["Інформація"].get_text(" ")) if "Інформація" in rows else ""
    heading = " ".join(clean_text(label.get_text(" ")) for label in panel.select(".panel-heading .label"))
    description_block = body.select_one("div[id$='--info']")
    semesters = _semesters(body, rows)
    credits = next((s.credits for s in semesters if s.credits is not None), None)
    if credits is None:
        credits = parse_float(_first(_CREDITS, info))

    def text_of(key: str) -> str:
        return clean_text(rows[key].get_text(" ")) if key in rows else ""

    return ParsedCourse(
        saz_code=code,
        saz_internal_id=internal_id_of(panel),
        title=title,
        credits=credits,
        hours=parse_int(_first(_HOURS, info)),
        recommended_year=parse_int(_first(_YEAR, info)),
        faculty=text_of("Факультет"),
        department=text_of("Кафедра"),
        level=text_of("Освітній рівень"),
        academic_year=text_of("Навчальний рік"),
        instructors=split_instructors(text_of("Викладач")),
        description=(clean_text(description_block.get_text(" ")) or None) if description_block else None,
        specialties=_specialties(body),
        semesters=semesters,
        happened="не відбувся" not in f"{heading} {info}",
    )
