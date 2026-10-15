// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setAccessToken } from "../../../api/token";
import { db } from "../../../mocks/db";
import { server } from "../../../mocks/server";
import { adminUserFixture } from "../../../test/handlers";
import { UsersPage } from "./UsersPage";
import { courseYearSourceLabel } from "./useUsers";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <UsersPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => setAccessToken("t"));

describe("courseYearSourceLabel", () => {
  it("називає джерела курсу українською", () => {
    expect(courseYearSourceLabel("self_declared")).toBe("Вказав студент");
    expect(courseYearSourceLabel("admin")).toBe("Адмін");
    expect(courseYearSourceLabel("saz_sync")).toBe("Синхронізація САЗ");
    expect(courseYearSourceLabel(null)).toBe("—");
  });
});

describe("UsersPage", () => {
  it("показує користувачів: ім'я, пошту, роль, курс, спеціальність, джерело курсу", async () => {
    renderPage();
    const student = await screen.findByRole("row", { name: /Владислав Смирнов/ });
    expect(within(student).getByText("vl.smyrnov@ukma.edu.ua")).toBeInTheDocument();
    expect(within(student).getByText("Студент")).toBeInTheDocument();
    expect(within(student).getByText("3")).toBeInTheDocument();
    expect(within(student).getByText("Вказав студент")).toBeInTheDocument();
    const admin = screen.getByRole("row", { name: /Адміністратор/ });
    expect(within(admin).getByText("Адмін")).toBeInTheDocument();
  });

  it("студент без курсу й адмін без профілю показують «—»", async () => {
    renderPage();
    const noCourse = await screen.findByRole("row", { name: /Андрій Мельник/ });
    expect(within(noCourse).getAllByText("—").length).toBeGreaterThanOrEqual(2);
    const admin = screen.getByRole("row", { name: /Адміністратор/ });
    expect(within(admin).getAllByText("—")).toHaveLength(3);
  });

  it("пошук надсилає q", async () => {
    let seen: URL | undefined;
    server.use(
      http.get("*/api/v1/admin/users", ({ request }) => {
        seen = new URL(request.url);
        return HttpResponse.json({
          users: [adminUserFixture()],
          pagination: { limit: 20, offset: 0, total: 1, has_more: false },
        });
      }),
    );
    renderPage();
    await screen.findByText("Владислав Смирнов");
    await userEvent.type(screen.getByLabelText("Пошук за поштою або ім'ям"), "смир");
    await waitFor(() => expect(seen?.searchParams.get("q")).toBe("смир"));
  });

  it("мок шукає без урахування регістру за поштою та ім'ям", async () => {
    renderPage();
    await screen.findByText("Владислав Смирнов");
    await userEvent.type(screen.getByLabelText("Пошук за поштою або ім'ям"), "O.KOVAL");
    await waitFor(() => expect(screen.queryByText("Владислав Смирнов")).not.toBeInTheDocument());
    expect(await screen.findByText("Олена Коваль")).toBeInTheDocument();
  });

  it("фільтр «Адміни» показує лише адмінів", async () => {
    renderPage();
    await screen.findByText("Владислав Смирнов");
    await userEvent.click(screen.getByRole("button", { name: "Адміни" }));
    await waitFor(() => expect(screen.queryByText("Владислав Смирнов")).not.toBeInTheDocument());
    expect(screen.getByText("Адміністратор")).toBeInTheDocument();
  });

  it("порожній результат: «Користувачів не знайдено»", async () => {
    db.admin.users = [];
    renderPage();
    expect(await screen.findByText("Користувачів не знайдено")).toBeInTheDocument();
  });
});
