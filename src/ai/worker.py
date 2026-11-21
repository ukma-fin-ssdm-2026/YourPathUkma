"""
FastAPI Background Task для AI-генерації плану.

Запускається після POST /plan-generations; виконує adapter.run() асинхронно.
Фронтенд опитує GET /plan-generations/{id} доки status != pending.

Використання ШІ: файл створено за допомогою Antigravity (Claude Sonnet 4.6, Google DeepMind)
за requirements.md (REL-001, PERF-001), AGENTS.md §5.
Перевірено: pytest tests/test_ai_worker.py, ruff check src/ai/worker.py.
"""

from __future__ import annotations

import logging

from . import adapter

logger = logging.getLogger("yourpath.ai.worker")


def run_generation_task(generation_id: int) -> None:
    """
    Точка входу для FastAPI BackgroundTask.
    Делегує виконання adapter.run(), який обробляє всі помилки всередині.
    """
    logger.info("BackgroundTask started: generation_id=%d", generation_id)
    try:
        adapter.run(generation_id)
    except Exception:
        # adapter.run() сам логує та позначає generation failed,
        # але на випадок непередбаченого виключення — логуємо тут теж
        logger.exception("Unhandled exception in BackgroundTask for generation_id=%d", generation_id)
    logger.info("BackgroundTask finished: generation_id=%d", generation_id)
