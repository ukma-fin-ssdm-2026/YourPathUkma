"""
Результат розбору каталогу САЗ. Вміст недовірений (R5, R7): тексти лише чистимо, не інтерпретуємо.

Використання ШІ: файл створено за допомогою Claude (Claude Code) за зразком розмітки сторінок
`my.ukma.edu.ua/course/catalog` (фікстури в tests/fixtures/saz). Перевірка: pytest.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class Specialty:
    name: str
    type: str  # як у САЗ: «Професійно-орієнтована», «Обов`язкова», ...


@dataclass(frozen=True)
class Semester:
    number: Optional[int]  # «Семестр 6» -> 6; None, якщо номери не вдалося зіставити з порами року
    season: str  # «Осінь» | «Весна» | «Літо»
    credits: Optional[float]


@dataclass
class ParsedCourse:
    saz_code: str
    saz_internal_id: Optional[str]  # id у `course-card-{id}`; не збігається з кодом курсу
    title: str
    credits: Optional[float] = None
    hours: Optional[int] = None
    recommended_year: Optional[int] = None  # «3 рік» з блоку «Інформація»
    faculty: str = ""
    department: str = ""
    level: str = ""
    academic_year: str = ""
    instructors: List[str] = field(default_factory=list)
    description: Optional[str] = None
    specialties: List[Specialty] = field(default_factory=list)
    semesters: List[Semester] = field(default_factory=list)
    happened: bool = True  # False для «Курс не відбувся»


@dataclass
class CardError:
    """Картка, яку не вдалося розібрати. Не валить усю сторінку."""

    internal_id: Optional[str]
    title: Optional[str]
    message: str


@dataclass
class CatalogPage:
    total: Optional[int]  # «Показані 1-20 із 1 712 записів» -> 1712
    last_page: Optional[int]  # None, якщо пагінації немає
    courses: List[ParsedCourse] = field(default_factory=list)
    errors: List[CardError] = field(default_factory=list)
