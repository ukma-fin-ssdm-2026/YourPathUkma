"""
Класифікація тижневого навантаження студента (AGENTS.md §4).

Використання ШІ: функцію й тести написано покроково за планом TDD за допомогою Claude (Anthropic).
Перевірка: pytest після кожного кроку, ruff, black, ручний огляд.
"""

LOW_LOAD_UPPER_BOUND = 20.0  # менше 20 год/тиждень: низьке
HIGH_LOAD_LOWER_BOUND = 23.0  # від 23 до 25 год/тиждень: високе
MAX_HOURS_PER_WEEK = 25.0


def classify_load_level(hours_per_week: float) -> str:
    """Повертає "low", "medium" або "high"; ValueError, якщо години поза діапазоном 0–25."""
    if not 0 <= hours_per_week <= MAX_HOURS_PER_WEEK:
        raise ValueError(f"Очікується 0–{MAX_HOURS_PER_WEEK:g} год/тиждень, отримано {hours_per_week:g}")
    if hours_per_week < LOW_LOAD_UPPER_BOUND:
        return "low"
    if hours_per_week < HIGH_LOAD_LOWER_BOUND:
        return "medium"
    return "high"
