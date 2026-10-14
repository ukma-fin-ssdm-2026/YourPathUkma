// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { RouterProvider, createMemoryRouter } from "react-router";
import type { PlanResponse } from "../../api/types";
import { server } from "../../mocks/server";
import { configHandler, planFixture, plansHandler } from "../../test/handlers";
import { PathLayout } from "./PathLayout";
import { PlansPage } from "./PlansPage";
import { courseHeading, groupPlansByCourse } from "./groupPlans";

describe("groupPlansByCourse", () => {
  it("групує за навчальним роком, найновіші зверху, плани за спаданням id", () => {
    const groups = groupPlansByCourse([
      planFixture({ id: 1, academic_year: 2025, course: 2 }),
      planFixture({ id: 2, academic_year: 2026, course: 3 }),
      planFixture({ id: 3, academic_year: 2026, course: 3 }),
    ]);
    expect(groups.map((g) => g.academic_year)).toEqual([2026, 2025]);
    expect(groups[0]!.plans.map((p) => p.id)).toEqual([3, 2]);
    expect(groups[1]!.course).toBe(2);
  });

  it("формує заголовок «3 курс · 2026/2027»", () => {
    expect(courseHeading({ course: 3, academic_year: 2026 })).toBe("3 курс · 2026/2027");
  });
});

function renderPlans(mode: "all" | "saved", entry = "/path/plan") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(
    [
      {
        path: "/path",
        element: <PathLayout />,
        children: [
          { path: "plan", element: <PlansPage mode="all" /> },
          { path: "saved", element: <PlansPage mode="saved" /> },
          { path: "create", element: <p>конструктор</p> },
        ],
      },
    ],
    { initialEntries: [mode === "saved" ? "/path/saved" : entry] },
  );
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

const draft = planFixture({ id: 1, status: "draft", total_credits: 58, free_elective_credits: 3 });
const approved = planFixture({
  id: 2,
  academic_year: 2024,
  course: 2,
  status: "approved",
  total_credits: 58.5,
  free_elective_credits: 3,
});

/** Стан «сервера» для тестів видалення: DELETE прибирає план зі списку. */
function statefulPlans(initial: PlanResponse[], deleteResponse?: () => Response) {
  let current = [...initial];
  server.use(
    http.get("*/api/v1/plans", () =>
      HttpResponse.json({
        plans: current,
        pagination: { limit: 100, offset: 0, total: current.length, has_more: false },
      }),
    ),
    http.delete("*/api/v1/plans/:id", ({ params }) => {
      if (deleteResponse) return deleteResponse();
      current = current.filter((plan) => String(plan.id) !== params.id);
      return new HttpResponse(null, { status: 204 });
    }),
  );
}

describe("PlansPage", () => {
  beforeEach(() => server.use(configHandler()));

  it("показує групи за курсами, статуси та кредити", async () => {
    server.use(plansHandler([draft, approved]));
    renderPlans("all");
    expect(await screen.findByText("3 курс · 2026/2027")).toBeInTheDocument();
    expect(screen.getByText("2 курс · 2024/2025")).toBeInTheDocument();
    expect(screen.getByText("Чернетка")).toBeInTheDocument();
    expect(screen.getByText("Затверджено")).toBeInTheDocument();
    expect(within(screen.getByTestId("plan-2")).getByText("58,5")).toBeInTheDocument();
  });

  it("чернетка має «Редагувати» і «Видалити», інші статуси лише «Переглянути»", async () => {
    server.use(plansHandler([draft, approved]));
    renderPlans("all");
    const draftRow = await screen.findByTestId("plan-1");
    expect(within(draftRow).getByRole("link", { name: "Редагувати" })).toHaveAttribute(
      "href",
      "/path/create?plan=1",
    );
    expect(within(draftRow).getByRole("button", { name: "Видалити" })).toBeInTheDocument();
    const approvedRow = screen.getByTestId("plan-2");
    expect(within(approvedRow).getByRole("link", { name: "Переглянути" })).toBeInTheDocument();
    expect(within(approvedRow).queryByRole("button", { name: "Видалити" })).not.toBeInTheDocument();
  });

  it("підтверджене видалення прибирає рядок", async () => {
    statefulPlans([draft, approved]);
    renderPlans("all");
    await userEvent.click(within(await screen.findByTestId("plan-1")).getByRole("button", { name: "Видалити" }));
    const dialog = screen.getByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Видалити" }));
    await waitFor(() => expect(screen.queryByTestId("plan-1")).not.toBeInTheDocument());
    expect(screen.getByTestId("plan-2")).toBeInTheDocument();
  });

  it("скасування й Esc закривають діалог без видалення", async () => {
    let deletes = 0;
    statefulPlans([draft], () => {
      deletes += 1;
      return new HttpResponse(null, { status: 204 });
    });
    renderPlans("all");
    const open = async () =>
      userEvent.click(within(await screen.findByTestId("plan-1")).getByRole("button", { name: "Видалити" }));
    await open();
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Скасувати" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await open();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(deletes).toBe(0);
    expect(screen.getByTestId("plan-1")).toBeInTheDocument();
  });

  it("409 PLAN_NOT_DELETABLE залишає рядок і пояснює причину", async () => {
    statefulPlans([draft], () =>
      HttpResponse.json({ code: "PLAN_NOT_DELETABLE", message: "x", details: [] }, { status: 409 }),
    );
    renderPlans("all");
    await userEvent.click(within(await screen.findByTestId("plan-1")).getByRole("button", { name: "Видалити" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Видалити" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Видаляти можна лише чернетки");
    expect(screen.getByTestId("plan-1")).toBeInTheDocument();
  });

  it("404 показує «План не знайдено»", async () => {
    statefulPlans([draft], () =>
      HttpResponse.json({ code: "PLAN_NOT_FOUND", message: "x", details: [] }, { status: 404 }),
    );
    renderPlans("all");
    await userEvent.click(within(await screen.findByTestId("plan-1")).getByRole("button", { name: "Видалити" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Видалити" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("План не знайдено");
  });

  it("порожній список пропонує створити план", async () => {
    server.use(plansHandler([]));
    renderPlans("all");
    expect(await screen.findByText("У вас ще немає планів")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Створити план" }).length).toBeGreaterThan(0);
  });

  it("«Оновити з САЗ» неактивна з поясненням, доки синхронізація вимкнена", async () => {
    server.use(plansHandler([draft]));
    renderPlans("all");
    const button = await screen.findByRole("button", { name: "Оновити з САЗ" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("title", expect.stringContaining("недоступн"));
  });

  it("запитує 100 планів; «Збережені» додають status=draft, «Індивідуальний» ні", async () => {
    const urls: URL[] = [];
    server.use(plansHandler([draft], (url) => urls.push(url)));
    renderPlans("all");
    await screen.findByTestId("plan-1");
    expect(urls[0]!.searchParams.get("limit")).toBe("100");
    expect(urls[0]!.searchParams.has("status")).toBe(false);

    const savedUrls: URL[] = [];
    server.use(plansHandler([draft], (url) => savedUrls.push(url)));
    renderPlans("saved");
    await waitFor(() => expect(savedUrls.at(-1)?.searchParams.get("status")).toBe("draft"));
  });
});

describe("PathLayout", () => {
  it("показує три підвкладки й позначає поточну", async () => {
    server.use(configHandler(), plansHandler([]));
    renderPlans("all");
    expect(await screen.findByRole("link", { name: "Індивідуальний план" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Збережені плани" })).not.toHaveAttribute("aria-current");
    const tabs = within(screen.getByRole("navigation", { name: "Науковий шлях" }));
    expect(tabs.getByRole("link", { name: "Створити план" })).toBeInTheDocument();
  });
});
