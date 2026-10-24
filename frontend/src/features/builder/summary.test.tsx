// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { render, screen, within } from "@testing-library/react";
import type { Credits, PlanItem, PlanValidationResponse, RuleIssue } from "../../api/types";
import type { BuilderPlan } from "./plan";
import { SummaryStrip } from "./SummaryStrip";

const credits: Credits = {
  total_used: 118.5,
  total_limit: 240,
  free_choice_used: 9,
  free_choice_limit: 25,
  professional_used: 27,
  professional_limit: 54,
};

const item = (id: number, credits: number, free = false): PlanItem => ({
  course_id: id,
  title: `Дисципліна ${id}`,
  trimester: 1,
  credits,
  is_free_elective: free,
});

const planWith = (items: PlanItem[]): BuilderPlan => ({
  academic_year: 2026,
  course: 3,
  load_levels: { autumn: "medium", spring: "medium", summer: "medium" },
  items,
});

function validation(
  overrides: Partial<PlanValidationResponse> & { total?: number; used?: number } = {},
): PlanValidationResponse {
  const { total = 0, used = 0, ...rest } = overrides;
  return {
    valid: true,
    errors: [],
    warnings: [],
    summary: {
      total_credits: total,
      free_elective_credits: 0,
      free_elective_used_all_years: used,
      free_elective_remaining: 25 - used,
      year_total_credits: total,
      credits_by_trimester: { "1": total, "2": 0, "3": 0 },
    },
    ...rest,
  };
}

const issue = (code: string, message = "повідомлення сервера"): RuleIssue => ({
  code,
  message,
  field: null,
});
const bar = (name: string) => screen.getByRole("progressbar", { name });
/** Число й підпис «з N» лежать у різних елементах, тож перевіряємо текст їхнього спільного контейнера. */
const metric = (suffix: string, full: string) =>
  expect(screen.getByText(suffix).parentElement).toHaveTextContent(full);

describe("SummaryStrip: числа", () => {
  it("порожній план без перевірки показує нулі", () => {
    render(
      <SummaryStrip
        plan={planWith([])}
        validation={undefined}
        credits={credits}
        normativeCredits={0}
      />,
    );
    metric("із 57–60", "0 із 57–60");
    expect(bar("Кредитів за рік")).toHaveAttribute("aria-valuenow", "0");
    expect(screen.getByText("Усе гаразд")).toBeInTheDocument();
  });

  it("кредити за рік це вибіркові з документа деканату разом з нормативними", () => {
    render(
      <SummaryStrip
        plan={planWith([item(1, 31)])}
        validation={validation({ total: 31 })}
        credits={credits}
        normativeCredits={27}
      />,
    );
    metric("із 57–60", "58 із 57–60");
    expect(bar("Кредитів за рік")).toHaveStyle({ width: "96.66666666666667%" });
  });

  it("вільний вибір за весь час береться з відповіді сервера", () => {
    render(
      <SummaryStrip
        plan={planWith([item(1, 5), item(2, 3, true)])}
        validation={validation({ total: 8, used: 12 })}
        credits={credits}
        normativeCredits={0}
      />,
    );
    metric("з 25", "12 з 25");
    expect(bar("Вільний вибір")).toHaveStyle({ width: "48%" });
  });

  it("без відповіді сервера вільний вибір рахується на клієнті з профілю та плану", () => {
    render(
      <SummaryStrip
        plan={planWith([item(1, 5), item(2, 3, true)])}
        validation={undefined}
        credits={credits}
        normativeCredits={0}
      />,
    );
    metric("з 25", "12 з 25");
  });

  it("профорієнтовні враховують профорієнтовні кредити цього плану", () => {
    render(
      <SummaryStrip
        plan={planWith([item(1, 5), item(2, 3, true)])}
        validation={undefined}
        credits={credits}
        normativeCredits={0}
      />,
    );
    metric("з 54", "32 з 54");
  });
});

describe("SummaryStrip: помилки й попередження", () => {
  it("помилка ліміту вільного вибору показується українською в alert", () => {
    render(
      <SummaryStrip
        plan={planWith([item(1, 5), item(2, 26, true)])}
        validation={validation({ total: 31, errors: [issue("FREE_ELECTIVE_LIMIT_EXCEEDED")] })}
        credits={credits}
        normativeCredits={27}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Перевищено ліміт вільного вибору (25 кредитів)",
    );
  });

  it("невідомий код показує повідомлення сервера", () => {
    render(
      <SummaryStrip
        plan={planWith([item(1, 5)])}
        validation={validation({ total: 5, errors: [issue("SOMETHING_NEW", "Нове правило")] })}
        credits={credits}
        normativeCredits={0}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Нове правило");
  });

  it("попередження про низьке навантаження не є помилкою", () => {
    render(
      <SummaryStrip
        plan={planWith([item(1, 31)])}
        validation={validation({ total: 31, warnings: [issue("LOW_LOAD_FUTURE_INCREASE")] })}
        credits={credits}
        normativeCredits={27}
      />,
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      screen.getAllByText("Низьке навантаження: наступні роки зростуть").length,
    ).toBeGreaterThan(0);
  });

  it("лічильник плашки дорівнює сумі помилок і попереджень", () => {
    render(
      <SummaryStrip
        plan={planWith([item(1, 31)])}
        validation={validation({
          total: 31,
          errors: [issue("DUPLICATE_COURSE")],
          warnings: [issue("LOW_LOAD_FUTURE_INCREASE")],
        })}
        credits={credits}
        normativeCredits={27}
      />,
    );
    expect(within(screen.getByTestId("issues-count")).getByText("2")).toBeInTheDocument();
  });

  it("серверне YEAR_CREDITS_BELOW_MIN ігнорується, бо сервер не бачить нормативних; рахуємо самі", () => {
    const serverWarn = validation({ total: 31, warnings: [issue("YEAR_CREDITS_BELOW_MIN")] });
    const { rerender } = render(
      <SummaryStrip
        plan={planWith([item(1, 31)])}
        validation={serverWarn}
        credits={credits}
        normativeCredits={27}
      />,
    );
    expect(screen.queryAllByText("За рік менше 57 кредитів")).toHaveLength(0);
    rerender(
      <SummaryStrip
        plan={planWith([item(1, 31)])}
        validation={serverWarn}
        credits={credits}
        normativeCredits={10}
      />,
    );
    expect(screen.getAllByText("За рік менше 57 кредитів").length).toBeGreaterThan(0);
  });
});
