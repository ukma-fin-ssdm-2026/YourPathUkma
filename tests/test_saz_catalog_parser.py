"""
Парсер сторінки каталогу САЗ на очищених фікстурах (без мережі).

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest.
"""

from pathlib import Path

from src.parser.parsers.catalog import CatalogParser

FIXTURES = Path(__file__).parent / "fixtures" / "saz"


def parse(name):
    return CatalogParser().parse((FIXTURES / name).read_text(encoding="utf-8"))


def test_first_page_summary_and_pagination():
    page = parse("catalog_page1.html")
    assert page.total == 1712  # «1&nbsp;712»
    assert page.last_page == 86
    assert len(page.courses) == 20
    assert page.errors == []


def test_filtered_catalog_has_two_pages():
    page = parse("catalog_filtered_26.html")
    assert (page.total, page.last_page, len(page.courses)) == (26, 2, 20)


def test_codes_are_unique_on_a_page():
    codes = [c.saz_code for c in parse("catalog_page1.html").courses]
    assert len(codes) == len(set(codes))


def test_broken_card_is_reported_not_fatal():
    html = (
        '<div class="summary">Показані <b>1-2</b> із <b>2</b> записів.</div>'
        '<div class="panel panel-default"><div class="panel-heading"><h4 class="panel-title">Без коду</h4></div>'
        '<div class="panel-collapse" id="course-card-7"><table><tr><th>Факультет</th><td>ФІ</td></tr></table>'
        "</div></div>"
    )
    page = CatalogParser().parse(html)
    assert page.courses == []
    assert [(e.internal_id, e.title) for e in page.errors] == [("7", "Без коду")]


def test_empty_or_unexpected_html():
    page = CatalogParser().parse("<html><body>Вхід</body></html>")
    assert (page.total, page.last_page, page.courses, page.errors) == (None, None, [], [])
