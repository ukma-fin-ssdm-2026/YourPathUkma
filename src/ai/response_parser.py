"""
Парсинг та валідація JSON-відповіді LLM (FR-009, FR-010).

Pydantic-схеми перевіряють структуру відповіді; серверна валідація course_id,
кількості альтернатив та ліміту вільного вибору виконується в adapter.py.

Використання ШІ: файл створено за допомогою Antigravity (Claude Sonnet 4.6, Google DeepMind)
за requirements.md (FR-009: 2–3 альтернативи на слот, FR-010: ліміт free_choice),
AGENTS.md §5. Перевірено: pytest tests/test_ai_response_parser.py, ruff check src/ai/response_parser.py.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Pydantic-схеми відповіді LLM
# ---------------------------------------------------------------------------


class LLMPlanItem(BaseModel):
    """Один слот у плані — дисципліна на конкретний триместр."""

    trimester: str = Field(..., description="autumn | spring | summer")
    course_id: int = Field(..., gt=0)
    category: str = Field(..., description="professional | free_choice")
    explanation: str = Field(default="", description="Пояснення українською")

    @field_validator("trimester")
    @classmethod
    def validate_trimester(cls, v: str) -> str:
        allowed = {"autumn", "spring", "summer"}
        if v not in allowed:
            raise ValueError(f"trimester must be one of {allowed}, got {v!r}")
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = {"professional", "free_choice"}
        if v not in allowed:
            raise ValueError(f"category must be one of {allowed}, got {v!r}")
        return v


class LLMAlternativeItem(BaseModel):
    """Одна альтернативна дисципліна."""

    course_id: int = Field(..., gt=0)
    explanation: str = Field(default="")


class LLMAlternativeSlot(BaseModel):
    """Альтернативи для конкретного слоту плану."""

    for_course_id: int = Field(..., gt=0)
    alternatives: list[LLMAlternativeItem] = Field(..., min_length=2, max_length=3)


class LLMNotice(BaseModel):
    """Повідомлення від LLM (наприклад, UNWANTED_INSTRUCTOR_UNAVOIDABLE)."""

    code: str = Field(..., max_length=64)
    message: str
    course_id: Optional[int] = Field(default=None)


class LLMResponse(BaseModel):
    """Верхній рівень відповіді LLM."""

    plan: list[LLMPlanItem] = Field(..., description="Список вибіркових дисциплін плану")
    alternatives: list[LLMAlternativeSlot] = Field(default_factory=list)
    notices: list[LLMNotice] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Парсинг
# ---------------------------------------------------------------------------


class ParseError(Exception):
    """Відповідь LLM неможливо розібрати або вона не проходить структурну валідацію."""

    pass


def _extract_json(text: str) -> str:
    """
    Витягує JSON з відповіді LLM.
    LLM може обгортати JSON у markdown-огорожі (```json ... ```) або повертати напряму.
    """
    # Спробувати витягти з markdown ```json...```
    md_match = re.search(r"```(?:json)?\s*(\{.*?})\s*```", text, re.DOTALL)
    if md_match:
        return md_match.group(1)

    # Знайти перший {...} у тексті
    brace_match = re.search(r"\{.*}", text, re.DOTALL)
    if brace_match:
        return brace_match.group(0)

    return text.strip()


def parse(raw_text: str) -> LLMResponse:
    """
    Парсить сирий текст відповіді LLM у структурований LLMResponse.
    Кидає ParseError якщо:
    - JSON не валідний
    - структура не відповідає схемі
    - кількість альтернатив < 2 або > 3 на слот (FR-009)
    """
    json_str = _extract_json(raw_text)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ParseError(f"Відповідь LLM не є валідним JSON: {exc}") from exc

    try:
        response = LLMResponse.model_validate(data)
    except Exception as exc:
        raise ParseError(f"Відповідь LLM не відповідає очікуваній схемі: {exc}") from exc

    # FR-009: кожен слот плану повинен мати 2–3 альтернативи
    plan_ids = {item.course_id for item in response.plan}
    alt_map = {slot.for_course_id for slot in response.alternatives}
    missing = plan_ids - alt_map
    if missing:
        raise ParseError(
            f"LLM не надав альтернативи для course_id: {sorted(missing)} (FR-009: 2–3 альтернативи на слот)"
        )

    return response
