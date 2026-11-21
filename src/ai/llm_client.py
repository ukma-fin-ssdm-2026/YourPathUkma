"""
HTTP-клієнт до Gemini API у OpenAI-сумісному режимі (REL-001, PERF-001).

Конфігурується через змінні оточення:
    LLM_API_KEY         — API-ключ Gemini (обов'язково)
    LLM_API_BASE_URL    — base URL (default: https://generativelanguage.googleapis.com/v1beta/openai)
    LLM_MODEL           — модель (default: gemini-2.0-flash)
    LLM_TIMEOUT_SECONDS — таймаут запиту (default: 300, PERF-001: ≤5 хв)
    LLM_MAX_RETRIES     — кількість повторних спроб при помилці (default: 2, REL-001: ≥2)

Використання ШІ: файл створено за допомогою Antigravity (Claude Sonnet 4.6, Google DeepMind)
за requirements.md (REL-001: retry ≥2, PERF-001: ≤5 хв), AGENTS.md §5.
Перевірено: pytest tests/test_ai_worker.py (mock LLM), ruff check src/ai/llm_client.py.
"""

from __future__ import annotations

import logging
import os
import time

import httpx

logger = logging.getLogger("yourpath.ai.llm_client")

_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
_DEFAULT_MODEL = "gemini-2.0-flash"
_DEFAULT_TIMEOUT = 300
_DEFAULT_MAX_RETRIES = 2


class LLMError(Exception):
    """Помилка LLM після вичерпання всіх спроб."""

    def __init__(self, message: str, attempts: int) -> None:
        super().__init__(message)
        self.attempts = attempts


def _get_config() -> dict:
    return {
        "api_key": os.environ.get("LLM_API_KEY", ""),
        "base_url": os.environ.get("LLM_API_BASE_URL", _DEFAULT_BASE_URL).rstrip("/"),
        "model": os.environ.get("LLM_MODEL", _DEFAULT_MODEL),
        "timeout": int(os.environ.get("LLM_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT)),
        "max_retries": int(os.environ.get("LLM_MAX_RETRIES", _DEFAULT_MAX_RETRIES)),
    }


def generate(system_prompt: str, user_prompt: str) -> tuple[str, int]:
    """
    Відправляє промпт до Gemini (OpenAI-режим) і повертає (response_text, attempts_used).
    При помилці мережі або HTTP 5xx — повторює до max_retries разів.
    При вичерпанні — кидає LLMError.

    REL-001: мінімум 2 повторних спроби.
    PERF-001: таймаут ≤ 300 с.
    """
    cfg = _get_config()
    api_key = cfg["api_key"]
    base_url = cfg["base_url"]
    model = cfg["model"]
    timeout = cfg["timeout"]
    max_retries = max(cfg["max_retries"], 2)  # REL-001: мінімум 2

    if not api_key:
        raise LLMError("LLM_API_KEY не задано", 0)

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
    }

    last_error: Exception | None = None
    attempts = 0

    for attempt in range(1, max_retries + 2):  # +2: 1 initial + max_retries retries
        attempts = attempt
        try:
            logger.info("LLM request attempt %d/%d model=%s", attempt, max_retries + 1, model)
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, headers=headers, json=payload)

            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                logger.info("LLM success attempt=%d chars=%d", attempt, len(content))
                return content, attempts

            # Retryable server errors
            if resp.status_code >= 500:
                last_error = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                logger.warning("LLM server error attempt=%d status=%d", attempt, resp.status_code)
            elif resp.status_code == 429:
                last_error = RuntimeError(f"HTTP 429 Rate limited: {resp.text[:200]}")
                logger.warning("LLM rate limited attempt=%d", attempt)
                time.sleep(5)
            else:
                # Non-retryable client error
                raise LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}", attempts)

        except httpx.TimeoutException as exc:
            last_error = exc
            logger.warning("LLM timeout attempt=%d", attempt)
        except httpx.RequestError as exc:
            last_error = exc
            logger.warning("LLM network error attempt=%d: %s", attempt, exc)

        if attempt < max_retries + 1:
            wait = 2**attempt
            logger.info("Retrying in %ds...", wait)
            time.sleep(wait)

    raise LLMError(f"LLM недоступний після {attempts} спроб: {last_error}", attempts)
