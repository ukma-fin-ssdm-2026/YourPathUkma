// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { RouterProvider, createMemoryRouter } from "react-router";
import type { AcademicRecord, AcademicYear } from "../../api/types";
import { useSession } from "../../auth/session";
import { authResponse, emptyMe } from "../../mocks/fixtures";
import { server } from "../../mocks/server";
import { configHandler } from "../../test/handlers";
import { CreditsLedger } from "./CreditsLedger";
import { LimitsStrip } from "./LimitsStrip";
import { ProfilePage, defaultPlanYear } from "./ProfilePage";
import { buildLedgerRow } from "./ledger";

let nextId = 1;
function rec(category: AcademicRecord["category"], credits: number, courseYear = 1): AcademicRecord {
  return {
    id: nextId++,
    academic_year: 2022 + courseYear,
    course_year: courseYear,
    course_id: null,
    title: `Дисципліна ${nextId}`,
    trimester: 1,
    credits,
    category,
    source: "self_declared",
    verified: false,
  };
}
const many = (category: AcademicRecord["category"], credits: number[], courseYear = 1) =>
  credits.map((value) => rec(category, value, courseYear));

const year1 = [...many("normative", [6, 6, 6, 6, 6, 6, 6]), ...many("professional", [6, 6]), ...many("free_choice", [3, 3])];
const year2 = [
  ...many("normative", [6, 6, 6, 6, 6, 6, 4.5], 2),
  ...many("professional", [5, 5, 5], 2),
  ...many("free_choice", [3], 2),
];
const years: AcademicYear[] = [
  { academic_year: 2023, course_year: 1, total_credits: 60, records: year1 },
  { academic_year: 2024, course_year: 2, total_credits: 58.5, records: year2 },
];

describe("buildLedgerRow", () => {
  it("рік 1: 42 / 12 / 6, без порожніх", () => {
    expect(buildLedgerRow(year1)).toEqual({ normative: 42, professional: 12, free_choice: 6, empty: 0 });
  });
  it("рік 2 з дробовими кредитами округлює накопичувально", () => {
    expect(buildLedgerRow(year2)).toEqual({ normative: 41, professional: 15, free_choice: 3, empty: 1 });
  });
  it("порожній список дає 60 порожніх клітинок", () => {
    expect(buildLedgerRow([])).toEqual({ normative: 0, professional: 0, free_choice: 0, empty: 60 });
  });
});

describe("defaultPlanYear", () => {
  it("бере поточний рік і тримає його в межах конфігурації", () => {
    expect(defaultPlanYear(new Date(2026, 9, 14), 2024, 2030)).toBe(2026);
    expect(defaultPlanYear(new Date(2031, 0, 1), 2024, 2030)).toBe(2030);
    expect(defaultPlanYear(new Date(2020, 0, 1), 2024, 2030)).toBe(2024);
  });
});

describe("CreditsLedger", () => {
  it("малює 4 рядки курсів і підсумок у підписі", () => {
    render(<CreditsLedger years={years} />);
    for (const label of ["1 курс", "2 курс", "3 курс", "4 курс"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(
      screen.getByRole("img", {
        name: "Набрано 118,5 кредитів: нормативні 82,5, профорієнтовні 27, вільний вибір 9",
      }),
    ).toBeInTheDocument();
    for (const label of ["Нормативні", "Профорієнтовні", "Вільний вибір"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });
});

describe("LimitsStrip", () => {
  it("показує ліміти й заповнення смужок", () => {
    render(
      <LimitsStrip
        credits={{
          total_used: 118.5,
          total_limit: 240,
          free_choice_used: 9,
          free_choice_limit: 25,
          professional_used: 27,
          professional_limit: 54,
        }}
      />,
    );
    expect(screen.getByText("з 54").parentElement).toHaveTextContent("27 з 54");
    expect(screen.getByText("з 25").parentElement).toHaveTextContent("9 з 25");
    expect(screen.getByRole("progressbar", { name: "Профорієнтовні" })).toHaveStyle({ width: "50%" });
    expect(screen.getByRole("progressbar", { name: "Вільний вибір" })).toHaveStyle({ width: "36%" });
  });
});

function renderProfile() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter([{ path: "/", element: <ProfilePage /> }], { initialEntries: ["/"] });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

function meWith(course: 1 | 2 | 3 | 4, canCreate: boolean) {
  const me = emptyMe();
  return {
    ...me,
    student: {
      ...me.student!,
      specialty: "Інженерія програмного забезпечення",
      course_year: course,
      onboarding_required: false,
      can_create_plan: canCreate,
      credits: {
        total_used: 118.5,
        total_limit: 240,
        free_choice_used: 9,
        free_choice_limit: 25,
        professional_used: 27,
        professional_limit: 54,
      },
    },
  };
}

describe("ProfilePage", () => {
  beforeEach(() => {
    useSession.getState().setAuthenticated(authResponse());
    server.use(configHandler());
  });

  it("показує курс, спеціальність, журнал і посилання на створення плану", async () => {
    server.use(http.get("*/api/v1/me", () => HttpResponse.json(meWith(3, true))));
    renderProfile();
    expect(await screen.findByText("3 курс · Інженерія програмного забезпечення")).toBeInTheDocument();
    const link = await screen.findByRole("link", { name: `Створити план на ${new Date().getFullYear()}` });
    expect(link).toHaveAttribute("href", "/path/create");
    expect(await screen.findByRole("img", { name: /Набрано 118,5 кредитів/ })).toBeInTheDocument();
  });

  it("для 1 курсу кнопка неактивна з поясненням", async () => {
    server.use(http.get("*/api/v1/me", () => HttpResponse.json(meWith(1, false))));
    renderProfile();
    expect(await screen.findByText("Для 1 курсу план формує деканат.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Створити план/ })).toBeDisabled();
    expect(screen.queryByRole("link", { name: /Створити план/ })).not.toBeInTheDocument();
  });
});
