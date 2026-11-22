"""
Тести для парсера сертифікатних програм та нормалізатора назв дисциплін (FR-013, AGENTS.md §4).

Використання ШІ: тести створено за допомогою Antigravity (Gemini 2.5 Pro).
Перевірка: pytest, ruff.
"""

from src.parser.parsers.certificates import (
    normalize_discipline_title,
    parse_catalog_page_html,
    parse_program_page_html,
)


def test_normalize_discipline_title_casing_and_spaces():
    raw = "   Бази   Даних та Інформаційні   Системи   "
    expected = "бази даних та інформаційні системи"
    assert normalize_discipline_title(raw) == expected


def test_normalize_discipline_title_apostrophes_and_dashes():
    raw_1 = "Компʼютерні мережі — базовий курс"
    raw_2 = "Комп'ютерні мережі – базовий курс"
    raw_3 = "Комп`ютерні мережі - базовий курс"

    expected = "комп'ютерні мережі - базовий курс"
    assert normalize_discipline_title(raw_1) == expected
    assert normalize_discipline_title(raw_2) == expected
    assert normalize_discipline_title(raw_3) == expected


def test_normalize_discipline_title_strips_parenthesized_notes():
    raw = "Хмарні технології (вибіркова)"
    assert normalize_discipline_title(raw) == "хмарні технології"

    raw_credits = "Аналіз даних (3 кредити)"
    assert normalize_discipline_title(raw_credits) == "аналіз даних"


def test_parse_catalog_page_html():
    html = """
    <html>
      <body>
        <h1>Сертифікатні програми НаУКМА</h1>
        <div class="menu">
          <a href="/certificate-programs/data-science">Data Science</a>
          <a href="/certificate-programs/cyber-security">Кібербезпека</a>
          <a href="https://other.com/promo">Реклама</a>
        </div>
      </body>
    </html>
    """
    programs = parse_catalog_page_html(html, base_url="https://vstup.ukma.edu.ua/certificate-programs")
    assert len(programs) == 2
    assert programs[0]["title"] == "Data Science"
    assert programs[0]["url"] == "https://vstup.ukma.edu.ua/certificate-programs/data-science"
    assert programs[1]["title"] == "Кібербезпека"


def test_parse_program_page_html_with_lists():
    html = """
    <html>
      <body>
        <h1>Data Science and Analytics</h1>
        <div class="description">
          <p>Ця сертифікатна програма готує спеціалістів з аналізу великих даних та машинного навчання.</p>
        </div>
        <h2>Обов'язкові дисципліни</h2>
        <ul>
          <li>Машинне навчання (обов'язкова)</li>
          <li>Глибинне навчання</li>
          <li>Великі дані в хмарі</li>
        </ul>
      </body>
    </html>
    """
    parsed = parse_program_page_html(html, source_url="https://vstup.ukma.edu.ua/certificate-programs/ds")
    assert parsed.title == "Data Science and Analytics"
    assert "машинного навчання" in parsed.description
    assert len(parsed.courses) == 3
    titles = [c.normalized_title for c in parsed.courses]
    assert "машинне навчання" in titles
    assert "глибинне навчання" in titles
    assert "великі дані в хмарі" in titles


def test_parse_program_page_html_with_table():
    html = """
    <html>
      <body>
        <h1>Кібербезпека</h1>
        <p>Програма з практичної кібербезпеки та захисту інфраструктури.</p>
        <table>
          <tr><th>№</th><th>Назва дисципліни</th></tr>
          <tr><td>1</td><td>Криптографічні протоколи</td></tr>
          <tr><td>2</td><td>Безпека веб-застосунків</td></tr>
        </table>
      </body>
    </html>
    """
    parsed = parse_program_page_html(html, source_url="https://vstup.ukma.edu.ua/certificate-programs/cs")
    assert parsed.title == "Кібербезпека"
    assert len(parsed.courses) == 2
    titles = [c.normalized_title for c in parsed.courses]
    assert "криптографічні протоколи" in titles
    assert "безпека веб-застосунків" in titles
