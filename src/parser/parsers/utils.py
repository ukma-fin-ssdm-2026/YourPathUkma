"""
Допоміжні функції розбору тексту САЗ.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: tests/test_saz_card_parser.py.
"""

import re
from typing import List, Optional

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def clean_text(value: Optional[str]) -> str:
    """Стискає пробіли (включно з nbsp) і обрізає краї."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def parse_int(value: Optional[str]) -> Optional[int]:
    """Перше ціле з рядка; «1 712» -> 1712; «необмежено» -> None."""
    if not value:
        return None
    text = clean_text(value)
    grouped = re.match(r"\d{1,3}(?: \d{3})+(?!\d)", text)
    if grouped:
        return int(grouped.group(0).replace(" ", ""))
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


def parse_float(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    match = _NUMBER.search(value)
    return float(match.group(0).replace(",", ".")) if match else None


def split_instructors(value: Optional[str]) -> List[str]:
    """
    «Д'яченко Ю.Ю., Тимкович В.В.» -> два прізвища; «Маслійчук В.Л., д.і.н.» -> одне (ступінь відкидається).
    Ступені й звання починаються з малої літери, прізвища з великої.
    """
    names: List[str] = []
    for token in clean_text(value).split(","):
        token = token.strip()
        if token and token[0].isupper():
            names.append(token)
    return names
