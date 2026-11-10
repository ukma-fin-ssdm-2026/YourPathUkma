"""Versioned SAZ catalog interchange shared by local scans and admin uploads.

Використання ШІ: схему імпорту створено Codex. Перевірка: pytest.
"""

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from ..db.enums import CourseKind

MAX_BUNDLE_BYTES = 25 * 1024 * 1024
MAX_COURSES = 4000
Text200 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class CatalogModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*")
    @classmethod
    def check_text(cls, value):
        values = value if isinstance(value, list) else [value]
        if any(isinstance(item, str) and "\x00" in item for item in values):
            raise ValueError("Текст дисципліни містить недопустимий символ")
        return value


class CatalogFields(CatalogModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)

    saz_code: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=2, max_length=300)
    description: str = Field(max_length=20000)
    credits: float = Field(gt=0, le=30)
    trimester: int = Field(ge=1, le=3)
    recommended_year: int = Field(ge=1, le=4)
    kind: CourseKind
    instructors: list[Text200] = Field(max_length=20)


class SemesterFields(CatalogModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    number: Optional[int]
    season: Literal["Осінь", "Весна", "Літо"]
    credits: Optional[float] = Field(ge=0)


class SpecialtyFields(CatalogModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=300)
    type: str = Field(max_length=300)


class BundleCourse(CatalogFields):
    happened: Optional[bool] = None
    semesters: list[SemesterFields] = Field(default_factory=list, max_length=12)
    specialties: list[SpecialtyFields] = Field(default_factory=list, max_length=100)
    faculty: str = Field(default="", max_length=300)
    department: str = Field(default="", max_length=300)
    level: str = Field(default="", max_length=100)
    academic_year: str = Field(default="", max_length=100)
    saz_internal_id: Optional[str] = Field(default=None, max_length=64)


class CatalogBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    academic_year: int = Field(ge=2000, le=2100, strict=True)
    level: Literal[1, 2]
    expected: int = Field(ge=0, strict=True)
    seen: int = Field(ge=1, strict=True)
    skipped: int = Field(ge=0, strict=True)
    pagination_changed: bool = Field(strict=True)
    courses: list[BundleCourse] = Field(min_length=1, max_length=MAX_COURSES)

    @model_validator(mode="after")
    def check_counts_and_codes(self):
        if len(self.courses) + self.skipped != self.seen:
            raise ValueError("Кількість дисциплін не відповідає лічильникам")
        if len({course.saz_code for course in self.courses}) != len(self.courses):
            raise ValueError("Коди дисциплін повторюються")
        return self
