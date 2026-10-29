"""
Парсер сторінки каталогу САЗ: кількість записів, остання сторінка пагінації, картки курсів.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: tests/test_saz_catalog_parser.py.
"""

from typing import List, Optional
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup, Tag

from ..models import CardError, CatalogPage
from .base import BaseParser
from .card import CardParseError, card_title_of, internal_id_of, parse_card
from .utils import parse_int


def iter_cards(soup: BeautifulSoup) -> List[Tag]:
    """Панелі курсів. Бічну панель студента відсікаємо: у ній немає `panel-heading` і `panel-collapse`."""
    return [
        panel
        for panel in soup.select("div.panel")
        if panel.select_one(":scope > .panel-heading") is not None
        and panel.select_one("div.panel-collapse[id^='course-card-']") is not None
    ]


def parse_total(soup: BeautifulSoup) -> Optional[int]:
    """«Показані 1-20 із 1 712 записів» -> 1712 (друге число в `div.summary`)."""
    bold = soup.select("div.summary b")
    return parse_int(bold[1].get_text()) if len(bold) >= 2 else None


def parse_last_page(soup: BeautifulSoup) -> Optional[int]:
    pagination = soup.select_one("ul.pagination")
    if pagination is None:
        return None
    last = pagination.select_one("li.last a")
    if last is not None:
        query = parse_qs(urlparse(str(last.get("href", ""))).query)
        if "page" in query and query["page"][0].isdigit():
            return int(query["page"][0])
        data_page = str(last.get("data-page", ""))
        if data_page.isdigit():
            return int(data_page) + 1
    numbers = [parse_int(a.get_text()) for a in pagination.select("li a")]
    numbers = [n for n in numbers if n is not None]
    return max(numbers) if numbers else None


class CatalogParser(BaseParser):
    def parse(self, html: str) -> CatalogPage:
        soup = BeautifulSoup(html, "lxml")
        page = CatalogPage(total=parse_total(soup), last_page=parse_last_page(soup))
        for panel in iter_cards(soup):
            try:
                page.courses.append(parse_card(panel))
            except CardParseError as exc:
                page.errors.append(CardError(internal_id_of(panel), card_title_of(panel), str(exc)))
        return page
