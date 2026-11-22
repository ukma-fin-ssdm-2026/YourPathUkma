"""
Парсер сертифікатних програм НаУКМА з сайту vstup.ukma.edu.ua (FR-013, AGENTS.md §4).

Витягує перелік програм, їхні описи та списки обов'язкових і вибіркових дисциплін.
Забезпечує нормалізацію назв для подальшої звірки з каталогом САЗ.

Використання ШІ: модуль створено за допомогою Antigravity (Gemini 2.5 Pro) за вимогами FR-013.
Перевірка: tests/test_certificates_parser.py, pytest, ruff.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_CERTIFICATES_URL = "https://vstup.ukma.edu.ua/certificate-programs"

# Заміна схожих візуально символів (латиниця -> кирилиця, апострофи, тире)
_CHAR_REPLACEMENTS = {
    "’": "'",
    "`": "'",
    "ʼ": "'",
    "“": '"',
    "”": '"',
    "«": '"',
    "»": '"',
    "–": "-",
    "—": "-",
    "−": "-",
}


def normalize_discipline_title(title: str) -> str:
    """
    Нормалізація назви дисципліни для стійкої звірки:
    1. NFKC нормалізація Unicode.
    2. Заміна типографічних лапок, апострофів, тире.
    3. Приведення до нижнього регістру.
    4. Очищення від зайвих пробілів і специфічних закінчень (наприклад '(вибіркова)', '3 кр.').
    """
    if not title:
        return ""
    text = unicodedata.normalize("NFKC", title)
    for src, dst in _CHAR_REPLACEMENTS.items():
        text = text.replace(src, dst)
    text = text.lower()
    # Видалення поміток у дужках на кшталт (вибіркова), (обов'язкова), (3 кредити) тощо
    text = re.sub(r"\((?:обов['ʼ]язкова|вибіркова|нормативна|\d+\s*(?:кр|кредит[а-я]*))\)", "", text)
    # Заміна послідовностей пробілів на один
    text = re.sub(r"\s+", " ", text).strip()
    # Прибирання крапки наприкінці
    text = text.rstrip(".")
    return text


@dataclass
class ParsedCertificateCourse:
    raw_title: str
    normalized_title: str
    is_mandatory: bool = True


@dataclass
class ParsedCertificateProgram:
    title: str
    source_url: str
    description: str = ""
    faculty: Optional[str] = None
    courses: List[ParsedCertificateCourse] = field(default_factory=list)


def parse_program_page_html(html: str, source_url: str, title: str = "") -> ParsedCertificateProgram:
    """Парсить окрему сторінку сертифікатної програми."""
    soup = BeautifulSoup(html, "html.parser")

    # Якщо заголовок не передано явно — шукаємо h1 або title
    if not title:
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)
        else:
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else "Невідома сертифікатна програма"

    # Опис програми
    desc_parts = []
    desc_container = (
        soup.find("div", class_=re.compile(r"description|content|entry-content", re.I))
        or soup.find("article")
        or soup.find("main")
    )
    if desc_container:
        paragraphs = desc_container.find_all("p")
        for p in paragraphs[:3]:
            text = p.get_text(strip=True)
            if text and len(text) > 20:
                desc_parts.append(text)
    description = "\n\n".join(desc_parts)

    courses: List[ParsedCertificateCourse] = []
    seen_titles = set()

    # Пошук списків дисциплін (теги <ul>, <ol>, <table> після заголовків зі словами 'дисциплін', 'компонент', 'план')
    headers = soup.find_all(re.compile(r"^h[2-4]$"))
    discipline_sections = []
    for h in headers:
        h_text = h.get_text(strip=True) if h else ""
        header_text = h_text.lower()
        if any(keyword in header_text for keyword in ["дисциплін", "курс", "предмет", "компонент", "програм"]):
            discipline_sections.append(h)

    # Якщо знайшли тематичні заголовки — беремо списки за ними
    elements_to_scan = []
    if discipline_sections:
        for h in discipline_sections:
            curr = h.find_next_sibling()
            while curr and curr.name not in ["h2", "h3"]:
                if curr.name in ["ul", "ol", "table"]:
                    elements_to_scan.append(curr)
                curr = curr.find_next_sibling()
    else:
        # Інакше скануємо всі списки та таблиці на сторінці
        elements_to_scan = soup.find_all(["ul", "ol", "table"])

    for elem in elements_to_scan:
        if elem.name in ["ul", "ol"]:
            for li in elem.find_all("li"):
                if li is None:
                    continue
                raw = li.get_text(strip=True)
                # Фільтруємо навігаційні та занадто короткі рядки
                if not raw or len(raw) < 4 or len(raw) > 250:
                    continue
                # Відкидаємо явні службові фрази
                if any(raw.lower().startswith(skip) for skip in ["головна", "контакти", "правила", "вартість"]):
                    continue
                norm = normalize_discipline_title(raw)
                if norm and norm not in seen_titles:
                    seen_titles.add(norm)
                    courses.append(ParsedCertificateCourse(raw_title=raw, normalized_title=norm))
        elif elem.name == "table":
            for tr in elem.find_all("tr"):
                tds = tr.find_all(["td", "th"])
                if not tds:
                    continue
                first_td = tds[0]
                if first_td is None:
                    continue
                raw = first_td.get_text(strip=True)
                # Якщо перший стовпець номер або код, беремо другий
                if len(tds) > 1 and (raw.isdigit() or len(raw) <= 3):
                    second_td = tds[1]
                    if second_td is None:
                        continue
                    raw = second_td.get_text(strip=True)
                if not raw or len(raw) < 4 or len(raw) > 250:
                    continue
                if any(header_word in raw.lower() for header_word in ["назва", "дисципліна", "номер", "№"]):
                    continue
                norm = normalize_discipline_title(raw)
                if norm and norm not in seen_titles:
                    seen_titles.add(norm)
                    courses.append(ParsedCertificateCourse(raw_title=raw, normalized_title=norm))

    return ParsedCertificateProgram(
        title=title,
        source_url=source_url,
        description=description,
        courses=courses,
    )


def parse_catalog_page_html(html: str, base_url: str = DEFAULT_CERTIFICATES_URL) -> List[dict]:
    """
    Парсить головну сторінку каталогу сертифікатних програм vstup.ukma.edu.ua/certificate-programs
    Повертає список словників: [{"title": ..., "url": ...}, ...]
    """
    soup = BeautifulSoup(html, "html.parser")
    programs = []
    seen_urls = set()

    for a in soup.find_all("a", href=True):
        if a is None:
            continue
        href = a.get("href", "")
        if not href:
            continue
        href = href.strip()
        title = a.get_text(strip=True) if a else ""
        # Посилання на сторінки сертифікатних програм
        if not title or len(title) < 3:
            continue
        full_url = urljoin(base_url, href)
        # Фільтруємо зовнішні посилання та якорі
        if "ukma.edu.ua" in full_url and full_url not in seen_urls:
            # Перевіряємо чи URL веде на сторінку сертифікатної програми
            if "/certificate" in full_url or "/programs" in full_url or "sert" in full_url:
                seen_urls.add(full_url)
                programs.append({"title": title, "url": full_url})

    return programs
