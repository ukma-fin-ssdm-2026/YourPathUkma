// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, delay } from "msw";
import { RouterProvider, createMemoryRouter } from "react-router";
import type { PlanItem } from "../../api/types";
import { setAccessToken } from "../../api/token";
import { server } from "../../mocks/server";
import { configFixture, configHandler, planFixture, plansCrudHandlers } from "../../test/handlers";
import { PlanViewPage } from "./PlanViewPage";

const item = (id: number, trimester: 1 | 2 | 3, credits: number, free = false, title = `Дисципліна ${id}`): PlanItem => ({
  course_id: id,
  title,
  trimester,
  credits,
  is_free_elective: free,
});

const plan = (overrides = {}) =>
  planFixture({
    id: 1,
    academic_year: 2026,
    course: 3,
    status: "draft",
    items: [item(1, 1, 5, false, "Функціональне програмування"), item(2, 2, 3, true, "Управління продуктом")],
    total_credits: 8,
    free_elective_credits: 3,
    load_levels: { autumn: "medium", spring: "high", summer: "low" },
    ...overrides,
  });

function renderPage(path = "/path/plan/1") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(
    [
      { path: "/path/plan/:id", element: <PlanViewPage /> },
      { path: "/path/plan", element: <p>список планів</p> },
      { path: "/path/create", element: <p>конструктор</p> },
    ],
    { initialEntries: [path] },
  );
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

const saved: string[] = [];
let click: { mockRestore: () => void };

beforeEach(() => {
  setAccessToken("t");
  saved.length = 0;
  Object.assign(URL, { createObjectURL: vi.fn(() => "blob:test"), revokeObjectURL: vi.fn() });
  click = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(function (this: HTMLAnchorElement) {
      saved.push(this.download);
    });
  server.use(configHandler(), ...plansCrudHandlers([plan()]).handlers);
});
afterEach(() => click.mockRestore());

describe("PlanViewPage: вміст", () => {
  it("показує заголовок, статус, метрики й дисципліни по триместрах", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: /План на 2026\/2027/ })).toBeInTheDocument();
    expect(screen.getByText("Чернетка")).toBeInTheDocument();
    expect(screen.getByText("Чернетка: ще можна редагувати")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Осінь" })).getByText("Функціональне програмування")).toBeInTheDocument();
    const spring = screen.getByRole("region", { name: "Весна" });
    expect(within(spring).getByText("Управління продуктом")).toBeInTheDocument();
    expect(within(spring).getByText("вільний вибір")).toBeInTheDocument();
    expect(within(spring).getByText("Навантаження: високе")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Осінь" })).getByText("Навантаження: середнє")).toBeInTheDocument();
  });

  it("порожній триместр каже, що дисциплін немає", async () => {
    renderPage();
    const summer = await screen.findByRole("region", { name: "Літо" });
    expect(within(summer).getByText("Дисциплін немає")).toBeInTheDocument();
    expect(within(summer).getByText("Навантаження: низьке")).toBeInTheDocument();
  });

  it("довга назва без пробілів переноситься", async () => {
    const longTitle = "Д".repeat(300);
    server.use(...plansCrudHandlers([plan({ items: [item(1, 1, 5, false, longTitle)] })]).handlers);
    renderPage();
    expect(await screen.findByText(longTitle)).toHaveClass("break-words");
  });

  it("лише чернетку можна редагувати", async () => {
    renderPage();
    expect(await screen.findByRole("link", { name: "Редагувати" })).toHaveAttribute("href", "/path/create?plan=1");
  });

  it("затверджений план без кнопки «Редагувати» і з відповідним підписом", async () => {
    server.use(...plansCrudHandlers([plan({ status: "approved" })]).handlers);
    renderPage();
    expect(await screen.findByText("Затверджено деканатом")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Редагувати" })).not.toBeInTheDocument();
  });

  it("посилання на відгуки безпечне, а «До списку планів» веде назад", async () => {
    renderPage();
    const reviews = await screen.findByRole("link", { name: /Почитати відгуки/ });
    expect(reviews).toHaveAttribute("href", "https://example.ukma.edu.ua/reviews");
    expect(reviews).toHaveAttribute("target", "_blank");
    expect(reviews).toHaveAttribute("rel", "noopener noreferrer");
    await userEvent.click(screen.getByRole("link", { name: "До списку планів" }));
    expect(await screen.findByText("список планів")).toBeInTheDocument();
  });
});

describe("PlanViewPage: недоступний план", () => {
  it.each([
    ["відсутній", "/path/plan/99"],
    ["некоректний id", "/path/plan/abc"],
  ])("%s показує «План не знайдено» з посиланням на список", async (_name, path) => {
    renderPage(path);
    expect(await screen.findByText("План не знайдено")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Індивідуальний план" })).toHaveAttribute("href", "/path/plan");
  });

  it("чужий план (403) показується так само", async () => {
    server.use(
      http.get("*/api/v1/plans/:id", () =>
        HttpResponse.json({ code: "PLAN_FORBIDDEN", message: "x", details: [] }, { status: 403 }),
      ),
    );
    renderPage();
    expect(await screen.findByText("План не знайдено")).toBeInTheDocument();
  });
});

describe("PlanViewPage: експорт PDF", () => {
  it("зберігає файл, а під час завантаження кнопка недоступна", async () => {
    server.use(
      http.get("*/api/v1/plans/:id/export", async () => {
        await delay(100);
        return new HttpResponse("%PDF-1.4", {
          headers: { "Content-Type": "application/pdf", "Content-Disposition": 'attachment; filename="plan-2026.pdf"' },
        });
      }),
    );
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Експорт PDF" }));
    expect(screen.getByRole("button", { name: "Готуємо PDF…" })).toBeDisabled();
    await waitFor(() => expect(saved).toEqual(["plan-2026.pdf"]));
    expect(await screen.findByRole("button", { name: "Експорт PDF" })).toBeEnabled();
  });

  it("помилка сервера показується, кнопка знову активна, файл не створюється", async () => {
    server.use(
      http.get("*/api/v1/plans/:id/export", () =>
        HttpResponse.json(
          { code: "INTERNAL_ERROR", message: "Збій сервера", details: [] },
          { status: 500, headers: { "X-Request-ID": "rid-5" } },
        ),
      ),
    );
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Експорт PDF" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Не вдалося підготувати PDF");
    expect(alert).toHaveTextContent("Код помилки: rid-5");
    expect(screen.getByRole("button", { name: "Експорт PDF" })).toBeEnabled();
    expect(saved).toEqual([]);
  });

  it("без прапорця plan_export кнопки немає", async () => {
    server.use(configHandler({ features: { ...configFixture().features, plan_export: false } }));
    renderPage();
    await screen.findByRole("heading", { name: /План на 2026\/2027/ });
    expect(screen.queryByRole("button", { name: "Експорт PDF" })).not.toBeInTheDocument();
  });
});
