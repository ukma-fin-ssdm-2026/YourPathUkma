"""
Recommendation Module — AI-генерація індивідуального навчального плану.

Компоненти:
- prompt_builder: побудова анонімізованого промпту для LLM
- llm_client: HTTP-клієнт до Gemini API (OpenAI-сумісний режим) з retry
- response_parser: Pydantic-валідація відповіді LLM
- adapter: оркестрація промпт → LLM → план
- worker: FastAPI BackgroundTask

Використання ШІ: пакет створено за допомогою Antigravity (Claude Sonnet 4.6, Google DeepMind)
за docs/requirements/requirements.md (FR-005, FR-006, FR-009, FR-010, REL-001, PERF-001)
та AGENTS.md §5. Перевірено: pytest tests/test_ai_*.py, ruff check src/ai.
"""
