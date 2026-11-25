"""
Генерація PDF-файлу індивідуального навчального плану.

Використовує fpdf2 із шрифтом DejaVu Sans для підтримки кирилиці/українських символів.
Генерує багатосторінковий PDF з таблицями дисциплін по триместрах.

Використання ШІ: файл створено за допомогою Antigravity (Gemini 2.5 Pro, Google DeepMind).
Перевірка: pytest (test_plan_export.py), ruff, ручна перевірка згенерованого PDF.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Sequence

from fpdf import FPDF

if TYPE_CHECKING:
    from ..db.models.deanery import NormativeCourseEntry
    from ..db.models.plans import IndividualPlan

_FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_DEJAVU = str(_FONTS_DIR / "DejaVuSans.ttf")
_DEJAVU_BOLD = str(_FONTS_DIR / "DejaVuSans-Bold.ttf")

_TRIMESTER_LABELS: Dict[str, str] = {
    "autumn": "Осінній триместр",
    "spring": "Весняний триместр",
    "summer": "Літній триместр",
}

_CATEGORY_LABELS: Dict[str, str] = {
    "professional": "Профорієнтовна",
    "free_choice": "Вільний вибір",
}


class _PlanPDF(FPDF):
    """PDF з шапкою і нижнім колонтитулом."""

    def __init__(self, student_name: str, academic_year: int) -> None:
        super().__init__()
        self._student_name = student_name
        self._academic_year = academic_year
        self.add_font("DejaVu", "", _DEJAVU)
        self.add_font("DejaVu", "B", _DEJAVU_BOLD)
        self.set_auto_page_break(auto=True, margin=20)

    def header(self) -> None:
        self.set_font("DejaVu", "B", 10)
        self.cell(0, 7, "НаУКМА — Факультет інформатики", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("DejaVu", "", 8)
        self.cell(
            0,
            5,
            f"Індивідуальний навчальний план на {self._academic_year}/{self._academic_year + 1} н. р.",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(3)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("DejaVu", "", 7)
        self.cell(0, 10, f"Сторінка {self.page_no()}/{{nb}}", align="C")


def _add_trimester_table(
    pdf: _PlanPDF,
    label: str,
    items: Sequence[tuple[str, str, float]],
) -> None:
    """Малює таблицю триместру: (назва, тип, кредити).

    Кожен рядок — multi_cell для довгих назв; розрив сторінки обробляє fpdf2 автоматично.
    """
    if not items:
        return

    pdf.set_font("DejaVu", "B", 10)
    pdf.cell(0, 8, label, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    # Ширини колонок: №(10), Назва(100), Тип(50), Кредити(30)
    col_w = (10, 100, 50, 30)
    pdf.set_font("DejaVu", "B", 8)
    headers = ("№", "Назва дисципліни", "Тип", "Кредити")
    for w, h in zip(col_w, headers):
        pdf.cell(w, 7, h, border=1, align="C")
    pdf.ln()

    pdf.set_font("DejaVu", "", 8)
    total_credits = 0.0
    for idx, (title, category, credits) in enumerate(items, 1):
        total_credits += credits
        x0 = pdf.get_x()
        y0 = pdf.get_y()

        # Визначаємо висоту рядка через multi_cell title
        line_h = pdf.font_size * 1.6
        title_width = col_w[1] - 2  # padding
        words = title.split()
        lines = 1
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip() if current_line else word
            if pdf.get_string_width(test_line) > title_width:
                lines += 1
                current_line = word
            else:
                current_line = test_line
        row_h = max(line_h * lines, 7)

        # Перевірка чи потрібна нова сторінка
        if y0 + row_h > pdf.h - pdf.b_margin:
            pdf.add_page()
            x0 = pdf.get_x()
            y0 = pdf.get_y()

        # № колонка
        pdf.set_xy(x0, y0)
        pdf.cell(col_w[0], row_h, str(idx), border=1, align="C")

        # Назва (multi_cell)
        pdf.set_xy(x0 + col_w[0], y0)
        pdf.multi_cell(col_w[1], line_h, title, border=1)
        after_title_y = pdf.get_y()
        actual_h = max(after_title_y - y0, row_h)

        # Виправляємо висоту № якщо multi_cell зайняв більше
        if actual_h > row_h:
            pdf.set_xy(x0, y0)
            pdf.cell(col_w[0], actual_h, str(idx), border=1, align="C")

        # Тип
        cat_label = _CATEGORY_LABELS.get(category, category)
        pdf.set_xy(x0 + col_w[0] + col_w[1], y0)
        pdf.cell(col_w[2], actual_h, cat_label, border=1, align="C")

        # Кредити
        pdf.set_xy(x0 + col_w[0] + col_w[1] + col_w[2], y0)
        pdf.cell(col_w[3], actual_h, str(credits), border=1, align="C")

        pdf.set_xy(x0, y0 + actual_h)

    # Підсумок по триместру
    pdf.set_font("DejaVu", "B", 8)
    sum_w = col_w[0] + col_w[1] + col_w[2]
    pdf.cell(sum_w, 7, "Усього за триместр:", border=1, align="R")
    pdf.cell(col_w[3], 7, str(round(total_credits, 1)), border=1, align="C")
    pdf.ln(10)


def _add_normative_table(
    pdf: _PlanPDF,
    normative_courses: Sequence[NormativeCourseEntry],
) -> None:
    """Таблиця нормативних дисциплін з документа деканату (якщо є)."""
    if not normative_courses:
        return

    # Групуємо по триместрах
    by_trimester: Dict[str, list[NormativeCourseEntry]] = {}
    for entry in normative_courses:
        key = entry.trimester.value
        by_trimester.setdefault(key, []).append(entry)

    pdf.set_font("DejaVu", "B", 11)
    pdf.cell(0, 10, "Нормативні дисципліни (з документа деканату)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    for tri_key in ("autumn", "spring", "summer"):
        entries = by_trimester.get(tri_key, [])
        if not entries:
            continue
        items = [(e.raw_title, "Нормативна", e.credits) for e in entries]
        _add_trimester_table(pdf, _TRIMESTER_LABELS[tri_key], items)


def generate_plan_pdf(
    plan: IndividualPlan,
    student_name: str,
    specialty: str | None,
    course_year: int,
    normative_courses: Sequence[NormativeCourseEntry] | None = None,
) -> bytes:
    """Генерує PDF-файл плану.

    Args:
        plan: ORM-план з завантаженими items (кожен item має .course).
        student_name: Повне ім'я студента.
        specialty: Спеціальність (або None).
        course_year: Рік навчання студента (2–4).
        normative_courses: Список нормативних дисциплін з документа деканату (якщо є).

    Returns:
        Байти PDF-файлу.
    """
    pdf = _PlanPDF(student_name, plan.academic_year)
    pdf.alias_nb_pages()
    pdf.add_page()

    # Інформація про студента
    pdf.set_font("DejaVu", "B", 11)
    pdf.cell(0, 10, "Інформація про студента", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 9)
    pdf.cell(0, 6, f"Студент: {student_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Курс: {course_year}", new_x="LMARGIN", new_y="NEXT")
    if specialty:
        pdf.cell(0, 6, f"Спеціальність: {specialty}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Статус плану: затверджений", new_x="LMARGIN", new_y="NEXT")
    if plan.title:
        pdf.cell(0, 6, f"Назва плану: {plan.title}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Вибіркові дисципліни по триместрах
    pdf.set_font("DejaVu", "B", 11)
    pdf.cell(0, 10, "Вибіркові дисципліни", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Групуємо елементи по триместрах
    by_trimester: Dict[str, list[tuple[str, str, float]]] = {"autumn": [], "spring": [], "summer": []}
    for item in plan.items:
        tri_key = item.trimester.value
        title = item.course.title
        category = item.category.value
        credits = item.course.credits
        by_trimester.setdefault(tri_key, []).append((title, category, credits))

    for tri_key in ("autumn", "spring", "summer"):
        items = by_trimester.get(tri_key, [])
        _add_trimester_table(pdf, _TRIMESTER_LABELS[tri_key], items)

    # Нормативні дисципліни (якщо передані)
    if normative_courses:
        _add_normative_table(pdf, normative_courses)

    # Загальний підсумок
    total_elective_credits = round(sum(item.course.credits for item in plan.items), 1)
    pdf.ln(5)
    pdf.set_font("DejaVu", "B", 10)
    pdf.cell(0, 8, f"Загальна кількість кредитів (вибіркові): {total_elective_credits}", new_x="LMARGIN", new_y="NEXT")

    if normative_courses:
        total_normative = round(sum(e.credits for e in normative_courses), 1)
        pdf.cell(0, 8, f"Загальна кількість кредитів (нормативні): {total_normative}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(
            0,
            8,
            f"Разом за навчальний рік: {round(total_elective_credits + total_normative, 1)}",
            new_x="LMARGIN",
            new_y="NEXT",
        )

    # Дата генерації
    pdf.ln(10)
    pdf.set_font("DejaVu", "", 7)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pdf.cell(0, 5, f"Згенеровано: {now}", new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
