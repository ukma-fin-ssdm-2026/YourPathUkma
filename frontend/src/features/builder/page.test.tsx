// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider, createMemoryRouter } from "react-router";
import type { DeaneryDocument, PlanItem } from "../../api/types";
import { useSession } from "../../auth/session";
import { db } from "../../mocks/db";
import { authResponse, normativeCourses } from "../../mocks/fixtures";
import { server } from "../../mocks/server";
import {
  configHandler,
  directionsHandler,
  disciplineFixture,
  disciplinesHandler,
  planFixture,
  plansCrudHandlers,
  validateHandler,
} from "../../test/handlers";
import { defaultPreferences } from "../preferences/preferences";
import { BuilderPage } from "./BuilderPage";

const MACHINE = disciplineFixture({ id: 5, title: "Машинне навчання", trimester: 2, credits: 6, directions: ["Data Science"] });
const FP = disciplineFixture({ id: 101, title: "Функціональне програмування", trimester: 1, credits: 5 });

function renderPage(entry = "/path/create?year=2026") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(
    [
      { path: "/path/create", element: <BuilderPage /> },
      { path: "/", element: <p>профіль</p> },
      { path: "/path/saved", element: <p>збережені</p> },
    ],
    { initialEntries: [entry] },
  );
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

function asStudent(course: 1 | 2 | 3 | 4) {
  const student = db.me.student!;
  db.me = {
    ...db.me,
    student: {
      ...student,
      course_year: course,
      onboarding_required: false,
      can_create_plan: course >= 2,
      load_levels_mode: course === 4 ? "auto" : "manual",
    },
  };
}

const column = (name: string) => screen.getByRole("region", { name });
const item = (id: number, trimester: 1 | 2 | 3, title = `Дисципліна ${id}`): PlanItem => ({
  course_id: id,
  title,
  trimester,
  credits: 5,
  is_free_elective: false,
});
const parsedDoc = (): DeaneryDocument => ({
  id: 1,
  academic_year: 2026,
  original_filename: "plan.pdf",
  mime_type: "pdf",
  size_bytes: 1000,
  parse_status: "parsed",
  parse_error: null,
  uploaded_at: "2026-10-08T10:00:00Z",
  normative_courses: normativeCourses(),
});

beforeEach(() => {
  useSession.getState().setAuthenticated(authResponse());
  asStudent(3);
  server.use(
    configHandler(),
    directionsHandler(["Data Science", "Cybersecurity"]),
    disciplinesHandler([FP, MACHINE]),
    validateHandler(),
  );
});

describe("BuilderPage: початковий стан", () => {
  it("новий план: три порожні колонки, нулі, а перевірка не надсилається", async () => {
    let validateCalls = 0;
    server.use(validateHandler(() => (validateCalls += 1)));
    renderPage();
    for (const name of ["Осінь", "Весна", "Літо"]) {
      expect(await screen.findByRole("region", { name })).toBeInTheDocument();
    }
    expect(screen.getByText("із 57–60").parentElement).toHaveTextContent("0 із 57–60");
    await new Promise((resolve) => setTimeout(resolve, 600));
    expect(validateCalls).toBe(0);
  });

  it("?plan=1 підвантажує елементи у відповідні колонки", async () => {
    const crud = plansCrudHandlers([
      planFixture({ id: 1, items: [item(1, 1, "Функціональне програмування"), item(2, 2, "Мова Haskell")] }),
    ]);
    server.use(...crud.handlers);
    renderPage("/path/create?year=2026&plan=1");
    expect(await within(await screen.findByRole("region", { name: "Осінь" })).findByText("Функціональне програмування")).toBeInTheDocument();
    expect(within(column("Весна")).getByText("Мова Haskell")).toBeInTheDocument();
  });

  it("початкове навантаження береться з побажань", async () => {
    db.preferences[2026] = {
      ...defaultPreferences(2026),
      load_levels: { autumn: "medium", spring: "medium", summer: "low" },
    };
    renderPage();
    const summer = await screen.findByRole("group", { name: "Навантаження: літо" });
    await waitFor(() => expect(within(summer).getByRole("button", { name: "Низьке" })).toHaveAttribute("aria-pressed", "true"));
  });

  it("для 4 курсу навантаження заблоковано", async () => {
    asStudent(4);
    renderPage();
    const autumn = await screen.findByRole("group", { name: "Навантаження: осінь" });
    await waitFor(() => {
      for (const button of within(autumn).getAllByRole("button")) expect(button).toBeDisabled();
    });
  });

  it("для 1 курсу замість конструктора пояснення й посилання на профіль", async () => {
    asStudent(1);
    renderPage();
    expect(await screen.findByText(/Для 1 курсу план формує деканат/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "До профілю" })).toHaveAttribute("href", "/");
    expect(screen.queryByRole("region", { name: "Осінь" })).not.toBeInTheDocument();
  });
});

describe("BuilderPage: додавання", () => {
  it("«+» кладе дисципліну в колонку її триместру", async () => {
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Додати Машинне навчання" }));
    expect(within(column("Весна")).getByText("Машинне навчання")).toBeInTheDocument();
    expect(within(column("Осінь")).queryByText("Машинне навчання")).not.toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Додати Машинне навчання" })).toBeDisabled();
  });

  it("тег залежить від напрямків із побажань", async () => {
    db.preferences[2026] = { ...defaultPreferences(2026), direction_ids: [1] };
    renderPage();
    const row = (await screen.findByText("Машинне навчання")).closest("div")!.parentElement!;
    await waitFor(() => expect(within(row).getByText("профорієнтовна")).toBeInTheDocument());
  });

  it("31-ша дисципліна не додається, причина показана", async () => {
    const thirty = Array.from({ length: 30 }, (_, i) => item(i + 1000, 1));
    server.use(...plansCrudHandlers([planFixture({ id: 1, items: thirty })]).handlers);
    renderPage("/path/create?year=2026&plan=1");
    await userEvent.click(await screen.findByRole("button", { name: "Додати Машинне навчання" }));
    expect(await screen.findByText("У плані може бути не більше 30 дисциплін")).toBeInTheDocument();
    expect(within(column("Весна")).queryByText("Машинне навчання")).not.toBeInTheDocument();
  });

  it("видалення з колонки прибирає дисципліну й знову відкриває «+»", async () => {
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Додати Машинне навчання" }));
    await userEvent.click(screen.getByRole("button", { name: "Прибрати Машинне навчання" }));
    expect(within(column("Весна")).queryByText("Машинне навчання")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Додати Машинне навчання" })).toBeEnabled();
  });
});

describe("BuilderPage: документ деканату", () => {
  it("нормативні показуються в колонках і входять у кредити за рік", async () => {
    db.documents.push(parsedDoc());
    renderPage();
    expect(await within(await screen.findByRole("region", { name: "Осінь" })).findByText("Архітектура ПЗ")).toBeInTheDocument();
    expect(within(column("Осінь")).getByText("від деканату")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText("із 57–60").parentElement).toHaveTextContent("29 із 57–60"),
    );
  });

  it("дисципліна, яку вже додав деканат, у каталозі недоступна", async () => {
    db.documents.push(parsedDoc());
    server.use(disciplinesHandler([disciplineFixture({ id: 301, title: "Архітектура ПЗ", trimester: 1 })]));
    renderPage();
    const button = await screen.findByRole("button", { name: "Додати Архітектура ПЗ" });
    await waitFor(() => expect(button).toBeDisabled());
    expect(screen.getAllByText("Додав деканат").length).toBeGreaterThan(0);
  });
});

describe("BuilderPage: недоступний план", () => {
  it("відсутній план: «План не знайдено»", async () => {
    server.use(...plansCrudHandlers([]).handlers);
    renderPage("/path/create?year=2026&plan=99");
    expect(await screen.findByText("План не знайдено")).toBeInTheDocument();
  });

  it("поданий план не можна редагувати", async () => {
    server.use(...plansCrudHandlers([planFixture({ id: 3, status: "submitted" })]).handlers);
    renderPage("/path/create?year=2026&plan=3");
    expect(await screen.findByText("Цей план уже подано, редагувати його не можна")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Збережені плани" })).toHaveAttribute("href", "/path/saved");
    expect(screen.queryByRole("region", { name: "Осінь" })).not.toBeInTheDocument();
  });
});
