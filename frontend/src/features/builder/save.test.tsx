// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { RouterProvider, createMemoryRouter } from "react-router";
import { ApiError } from "../../api/errors";
import type { PlanItem } from "../../api/types";
import { useSession } from "../../auth/session";
import { db } from "../../mocks/db";
import { authResponse } from "../../mocks/fixtures";
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
import { BuilderPage } from "./BuilderPage";
import { describeSaveError } from "./saveErrors";

const MACHINE = disciplineFixture({ id: 5, title: "Машинне навчання", trimester: 2, credits: 6, directions: ["Data Science"] });
const HASKELL = disciplineFixture({ id: 6, title: "Мова Haskell", trimester: 1, credits: 5, directions: ["Data Science"] });

const items: PlanItem[] = [
  { course_id: 5, title: "Машинне навчання", trimester: 2, credits: 6, is_free_elective: false },
  { course_id: 6, title: "Мова Haskell", trimester: 1, credits: 5, is_free_elective: true },
];

describe("describeSaveError", () => {
  it("422 по елементу: повідомлення за кодом біля course_id цього елемента", () => {
    const error = new ApiError(422, "VALIDATION_ERROR", "x", [
      { field: "items.1.course_id", message: "COURSE_DATA_MISMATCH: у каталозі інші кредити" },
      { field: "items.0.course_id", message: "NORMATIVE_NOT_ALLOWED: нормативна" },
    ]);
    expect(describeSaveError(error, items)).toEqual({
      itemErrors: {
        6: "Кредити або триместр не збігаються з каталогом",
        5: "Нормативну дисципліну додає деканат",
      },
      form: [],
    });
  });

  it("422 рівня плану з бекенду: відомий код перекладається, невідомий втрачає префікс", () => {
    const error = new ApiError(422, "VALIDATION_ERROR", "x", [
      { field: "items", message: "ONLY_FREE_ELECTIVES: Не можна обрати лише вільний вибір" },
      { field: "items", message: "NORMATIVE_CONFLICT: Дисципліна вже є в документі деканату" },
    ]);
    expect(describeSaveError(error, items).form).toEqual([
      "Оберіть хоча б одну профорієнтовну дисципліну",
      "Дисципліна вже є в документі деканату",
    ]);
  });

  it("COURSE_NOT_FOUND пояснюється", () => {
    const error = new ApiError(422, "VALIDATION_ERROR", "x", [
      { field: "items.0.course_id", message: "COURSE_NOT_FOUND: немає" },
    ]);
    expect(describeSaveError(error, items).itemErrors).toEqual({ 5: "Дисципліни немає в каталозі" });
  });

  it("422 рівня тіла іде у form без префікса Value error", () => {
    const error = new ApiError(422, "VALIDATION_ERROR", "x", [
      { field: "body", message: "Value error, Перевищено ліміт вільного вибору: 28.0 > 25 кредитів" },
    ]);
    expect(describeSaveError(error, items)).toEqual({
      itemErrors: {},
      form: ["Перевищено ліміт вільного вибору: 28.0 > 25 кредитів"],
    });
  });

  it("409 коди мають людські тексти", () => {
    expect(describeSaveError(new ApiError(409, "PLAN_NOT_EDITABLE", "x"), items).form).toEqual([
      "Цей план уже подано, редагувати його не можна",
    ]);
    expect(describeSaveError(new ApiError(409, "PLAN_NOT_SUBMITTABLE", "x"), items).form).toEqual([
      "Подати можна лише чернетку",
    ]);
  });

  it("PLAN_VALIDATION_FAILED виводить details списком", () => {
    const error = new ApiError(422, "PLAN_VALIDATION_FAILED", "x", [
      { field: "", message: "За рік менше 57 кредитів" },
    ]);
    expect(describeSaveError(error, items).form).toEqual(["За рік менше 57 кредитів"]);
  });

  it("невідома помилка показує повідомлення сервера", () => {
    expect(describeSaveError(new ApiError(500, "INTERNAL_ERROR", "Збій сервера"), items).form).toEqual([
      "Збій сервера",
    ]);
  });
});

function renderPage(entry = "/path/create?year=2026") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(
    [
      { path: "/path/create", element: <BuilderPage /> },
      { path: "/path/plan", element: <p>список планів</p> },
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

function asStudent3() {
  const student = db.me.student!;
  db.me = {
    ...db.me,
    student: { ...student, course_year: 3, onboarding_required: false, can_create_plan: true, load_levels_mode: "manual" },
  };
}

const add = async (title: string) => userEvent.click(await screen.findByRole("button", { name: `Додати ${title}` }));
const saveButton = () => screen.getByRole("button", { name: "Зберегти чернетку" });
const submitButton = () => screen.getByRole("button", { name: "Подати на розгляд" });

beforeEach(() => {
  useSession.getState().setAuthenticated(authResponse());
  asStudent3();
  server.use(
    configHandler(),
    directionsHandler(["Data Science"]),
    disciplinesHandler([MACHINE, HASKELL]),
    validateHandler(),
  );
});

describe("збереження чернетки", () => {
  it("порожній план: обидві кнопки недоступні", async () => {
    renderPage();
    await screen.findByRole("region", { name: "Осінь" });
    expect(saveButton()).toBeDisabled();
    expect(submitButton()).toBeDisabled();
  });

  it("перше збереження це POST із повним тілом, наступне це PUT, а адреса отримує plan=id", async () => {
    const crud = plansCrudHandlers();
    server.use(...crud.handlers);
    const router = renderPage();
    await add("Машинне навчання");
    await userEvent.click(saveButton());
    expect(await screen.findByText(/^Збережено/)).toBeInTheDocument();
    expect(crud.bodies[0]).toMatchObject({
      academic_year: 2026,
      course: 3,
      load_levels: { autumn: "medium", spring: "medium", summer: "medium" },
      items: [{ course_id: 5, title: "Машинне навчання", trimester: 2, credits: 6 }],
    });
    await waitFor(() => expect(router.state.location.search).toContain("plan=1"));

    await add("Мова Haskell");
    expect(screen.queryByText(/^Збережено/)).not.toBeInTheDocument();
    await userEvent.click(saveButton());
    await screen.findByText(/^Збережено/);
    expect(crud.calls).toMatchObject({ post: 1, put: 1 });
    expect(crud.bodies[1]!.items).toHaveLength(2);
  });

  it("422 по елементу показується біля картки", async () => {
    server.use(
      http.post("*/api/v1/plans", () =>
        HttpResponse.json(
          {
            code: "VALIDATION_ERROR",
            message: "x",
            details: [{ field: "items.0.course_id", message: "COURSE_DATA_MISMATCH: у каталозі інші кредити" }],
          },
          { status: 422 },
        ),
      ),
    );
    renderPage();
    await add("Машинне навчання");
    await userEvent.click(saveButton());
    const card = await screen.findByTestId("item-5");
    expect(await within(card).findByText("Кредити або триместр не збігаються з каталогом")).toBeInTheDocument();
  });

  it("422 рівня тіла показується списком над планом", async () => {
    server.use(
      http.post("*/api/v1/plans", () =>
        HttpResponse.json(
          {
            code: "VALIDATION_ERROR",
            message: "x",
            details: [{ field: "body", message: "Value error, Перевищено ліміт вільного вибору: 28.0 > 25 кредитів" }],
          },
          { status: 422 },
        ),
      ),
    );
    renderPage();
    await add("Машинне навчання");
    await userEvent.click(saveButton());
    expect(await screen.findByText("Перевищено ліміт вільного вибору: 28.0 > 25 кредитів")).toBeInTheDocument();
  });

  it("409 PLAN_NOT_EDITABLE пояснюється", async () => {
    server.use(...plansCrudHandlers([planFixture({ id: 1, status: "draft", items })]).handlers);
    server.use(
      http.put("*/api/v1/plans/1", () =>
        HttpResponse.json({ code: "PLAN_NOT_EDITABLE", message: "x", details: [] }, { status: 409 }),
      ),
    );
    renderPage("/path/create?year=2026&plan=1");
    await screen.findByRole("region", { name: "Осінь" });
    await userEvent.click(screen.getByRole("button", { name: "Прибрати Мова Haskell" }));
    await userEvent.click(saveButton());
    expect(await screen.findByText("Цей план уже подано, редагувати його не можна")).toBeInTheDocument();
  });
});

describe("подання", () => {
  it("підтвердження зберігає й подає план, далі веде до списку планів", async () => {
    const crud = plansCrudHandlers();
    let submits = 0;
    server.use(
      ...crud.handlers,
      http.post("*/api/v1/plans/:id/submit", ({ params }) => {
        submits += 1;
        return HttpResponse.json(planFixture({ id: Number(params.id), status: "submitted" }));
      }),
    );
    renderPage();
    await add("Машинне навчання");
    await userEvent.click(submitButton());
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Подати план?")).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Подати" }));
    expect(await screen.findByText("список планів")).toBeInTheDocument();
    expect(crud.calls.post).toBe(1);
    expect(submits).toBe(1);
  });

  it("скасування діалогу нічого не надсилає", async () => {
    const crud = plansCrudHandlers();
    server.use(...crud.handlers);
    renderPage();
    await add("Машинне навчання");
    await userEvent.click(submitButton());
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Скасувати" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(crud.calls.post).toBe(0);
  });

  it("409 PLAN_NOT_SUBMITTABLE лишає користувача на сторінці з поясненням", async () => {
    server.use(
      ...plansCrudHandlers().handlers,
      http.post("*/api/v1/plans/:id/submit", () =>
        HttpResponse.json({ code: "PLAN_NOT_SUBMITTABLE", message: "x", details: [] }, { status: 409 }),
      ),
    );
    renderPage();
    await add("Машинне навчання");
    await userEvent.click(submitButton());
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Подати" }));
    expect(await screen.findByText("Подати можна лише чернетку")).toBeInTheDocument();
    expect(screen.queryByText("список планів")).not.toBeInTheDocument();
  });
});

describe("незбережені зміни", () => {
  const fireUnload = () => {
    const event = new Event("beforeunload", { cancelable: true });
    act(() => void window.dispatchEvent(event));
    return event.defaultPrevented;
  };

  it("beforeunload блокується лише коли є незбережені зміни", async () => {
    server.use(...plansCrudHandlers().handlers);
    renderPage();
    await screen.findByRole("region", { name: "Осінь" });
    expect(fireUnload()).toBe(false);
    await add("Машинне навчання");
    expect(fireUnload()).toBe(true);
    await userEvent.click(saveButton());
    await screen.findByText(/^Збережено/);
    expect(fireUnload()).toBe(false);
  });
});
