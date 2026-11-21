"""
Unit-тести response_parser.py: парсинг та валідація JSON-відповіді LLM.

Використання ШІ: файл створено за допомогою Antigravity (Claude Sonnet 4.6, Google DeepMind)
за requirements.md (FR-009: 2–3 альтернативи на слот).
Перевірено: pytest tests/test_ai_response_parser.py, ruff check.
"""

import json

import pytest

from src.ai.response_parser import LLMResponse, ParseError, parse

# ---------------------------------------------------------------------------
# Валідна відповідь для повторного використання
# ---------------------------------------------------------------------------

VALID_RESPONSE = {
    "plan": [
        {
            "trimester": "autumn",
            "course_id": 101,
            "category": "professional",
            "explanation": "Корисна дисципліна для розвитку навичок",
        },
        {
            "trimester": "spring",
            "course_id": 102,
            "category": "free_choice",
            "explanation": "Розширює кругозір",
        },
    ],
    "alternatives": [
        {
            "for_course_id": 101,
            "alternatives": [
                {"course_id": 201, "explanation": "Альтернатива 1"},
                {"course_id": 202, "explanation": "Альтернатива 2"},
            ],
        },
        {
            "for_course_id": 102,
            "alternatives": [
                {"course_id": 203, "explanation": "Альтернатива A"},
                {"course_id": 204, "explanation": "Альтернатива B"},
                {"course_id": 205, "explanation": "Альтернатива C"},
            ],
        },
    ],
    "notices": [],
}


def valid_json() -> str:
    return json.dumps(VALID_RESPONSE)


# ---------------------------------------------------------------------------
# Успішний парсинг
# ---------------------------------------------------------------------------


def test_parse_valid_json_returns_llm_response():
    result = parse(valid_json())
    assert isinstance(result, LLMResponse)
    assert len(result.plan) == 2
    assert len(result.alternatives) == 2


def test_parse_plan_items_have_correct_fields():
    result = parse(valid_json())
    item = result.plan[0]
    assert item.trimester == "autumn"
    assert item.course_id == 101
    assert item.category == "professional"
    assert "Корисна" in item.explanation


def test_parse_alternatives_count_per_slot():
    result = parse(valid_json())
    assert len(result.alternatives[0].alternatives) == 2
    assert len(result.alternatives[1].alternatives) == 3


def test_parse_notices_empty_list():
    result = parse(valid_json())
    assert result.notices == []


def test_parse_notice_with_code():
    data = dict(VALID_RESPONSE)
    data["notices"] = [{"code": "UNWANTED_INSTRUCTOR_UNAVOIDABLE", "message": "Небажаний викладач", "course_id": 101}]
    result = parse(json.dumps(data))
    assert len(result.notices) == 1
    assert result.notices[0].code == "UNWANTED_INSTRUCTOR_UNAVOIDABLE"
    assert result.notices[0].course_id == 101


# ---------------------------------------------------------------------------
# Markdown-огорожа
# ---------------------------------------------------------------------------


def test_parse_handles_markdown_json_fence():
    wrapped = f"```json\n{valid_json()}\n```"
    result = parse(wrapped)
    assert len(result.plan) == 2


def test_parse_handles_json_fence_without_language():
    wrapped = f"```\n{valid_json()}\n```"
    result = parse(wrapped)
    assert len(result.plan) == 2


def test_parse_handles_text_before_json():
    text = f"Ось мій план:\n\n{valid_json()}"
    result = parse(text)
    assert len(result.plan) == 2


# ---------------------------------------------------------------------------
# Помилки парсингу
# ---------------------------------------------------------------------------


def test_parse_raises_on_invalid_json():
    with pytest.raises(ParseError, match="валідним JSON"):
        parse("це не JSON {{{")


def test_parse_raises_on_missing_plan_key():
    with pytest.raises(ParseError):
        parse(json.dumps({"alternatives": [], "notices": []}))


def test_parse_raises_on_wrong_trimester_value():
    data = dict(VALID_RESPONSE)
    data["plan"] = [{"trimester": "invalid", "course_id": 101, "category": "professional", "explanation": ""}]
    with pytest.raises(ParseError):
        parse(json.dumps(data))


def test_parse_raises_on_wrong_category_value():
    data = dict(VALID_RESPONSE)
    data["plan"] = [{"trimester": "autumn", "course_id": 101, "category": "unknown", "explanation": ""}]
    with pytest.raises(ParseError):
        parse(json.dumps(data))


def test_parse_raises_when_alternatives_missing_for_slot():
    """FR-009: кожен слот плану повинен мати альтернативи."""
    data = dict(VALID_RESPONSE)
    # Є план з 2 курсами, але альтернативи тільки для одного
    data["alternatives"] = [
        {
            "for_course_id": 101,
            "alternatives": [
                {"course_id": 201, "explanation": "Alt1"},
                {"course_id": 202, "explanation": "Alt2"},
            ],
        }
    ]
    with pytest.raises(ParseError, match="FR-009"):
        parse(json.dumps(data))


def test_parse_raises_on_too_few_alternatives():
    """FR-009: мінімум 2 альтернативи на слот."""
    data = dict(VALID_RESPONSE)
    data["alternatives"] = [
        {
            "for_course_id": 101,
            "alternatives": [{"course_id": 201, "explanation": "Лише одна"}],  # < 2
        },
        {
            "for_course_id": 102,
            "alternatives": [
                {"course_id": 203, "explanation": "Alt A"},
                {"course_id": 204, "explanation": "Alt B"},
            ],
        },
    ]
    with pytest.raises(ParseError):
        parse(json.dumps(data))


def test_parse_raises_on_too_many_alternatives():
    """FR-009: максимум 3 альтернативи на слот."""
    data = dict(VALID_RESPONSE)
    data["alternatives"] = [
        {
            "for_course_id": 101,
            "alternatives": [
                {"course_id": 201, "explanation": "1"},
                {"course_id": 202, "explanation": "2"},
                {"course_id": 203, "explanation": "3"},
                {"course_id": 204, "explanation": "4"},  # > 3
            ],
        },
        {
            "for_course_id": 102,
            "alternatives": [
                {"course_id": 205, "explanation": "A"},
                {"course_id": 206, "explanation": "B"},
            ],
        },
    ]
    with pytest.raises(ParseError):
        parse(json.dumps(data))


# ---------------------------------------------------------------------------
# Крайні випадки
# ---------------------------------------------------------------------------


def test_parse_empty_plan_is_valid():
    """Порожній план — LLM може повернути порожній список (edge case)."""
    data = {"plan": [], "alternatives": [], "notices": []}
    result = parse(json.dumps(data))
    assert result.plan == []


def test_parse_explanation_defaults_to_empty_string():
    data = {
        "plan": [{"trimester": "autumn", "course_id": 101, "category": "professional"}],
        "alternatives": [
            {
                "for_course_id": 101,
                "alternatives": [{"course_id": 201}, {"course_id": 202}],
            }
        ],
        "notices": [],
    }
    result = parse(json.dumps(data))
    assert result.plan[0].explanation == ""
    assert result.alternatives[0].alternatives[0].explanation == ""
