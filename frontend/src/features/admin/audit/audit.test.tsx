// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setAccessToken } from "../../../api/token";
import { db } from "../../../mocks/db";
import { server } from "../../../mocks/server";
import { auditEntryFixture } from "../../../test/handlers";
import { AuditPage } from "./AuditPage";
import { outcomeLabel } from "./useAudit";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AuditPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => setAccessToken("t"));

describe("outcomeLabel", () => {
  it("називає результати українською", () => {
    expect(outcomeLabel("allowed")).toBe("Дозволено");
    expect(outcomeLabel("denied")).toBe("Відмовлено");
  });
});

describe("AuditPage", () => {
  it("показує час, виконавця, дію, об'єкт, результат і IP", async () => {
    renderPage();
    const denied = await screen.findByRole("row", { name: /plan\.read/ });
    expect(within(denied).getByText("Владислав Смирнов")).toBeInTheDocument();
    expect(within(denied).getByText("IndividualPlan #3")).toBeInTheDocument();
    expect(within(denied).getByText("Відмовлено")).toBeInTheDocument();
    expect(within(denied).getByText("10.0.0.15")).toBeInTheDocument();
  });

  it("анонімна спроба позначена «Анонімно»", async () => {
    db.admin.auditLog = [auditEntryFixture({ id: 1, actor: null, action: "auth.login" })];
    renderPage();
    const row = await screen.findByRole("row", { name: /auth\.login/ });
    expect(within(row).getByText("Анонімно")).toBeInTheDocument();
  });

  it("запитує по 50 записів", async () => {
    let seen: URL | undefined;
    server.use(
      http.get("*/api/v1/admin/audit-log", ({ request }) => {
        seen = new URL(request.url);
        return HttpResponse.json({
          audit_log: [],
          pagination: { limit: 50, offset: 0, total: 0, has_more: false },
        });
      }),
    );
    renderPage();
    expect(await screen.findByText("Записів немає")).toBeInTheDocument();
    expect(seen?.searchParams.get("limit")).toBe("50");
  });

  it("фільтр результату «Відмовлено» залишає лише відмови", async () => {
    renderPage();
    await screen.findByRole("row", { name: /user\.update/ });
    await userEvent.click(screen.getByRole("button", { name: "Відмовлено" }));
    await waitFor(() => expect(screen.queryByRole("row", { name: /user\.update/ })).not.toBeInTheDocument());
    expect(screen.getByRole("row", { name: /plan\.read/ })).toBeInTheDocument();
  });

  it("фільтр дії надсилає action", async () => {
    let seen: URL | undefined;
    server.use(
      http.get("*/api/v1/admin/audit-log", ({ request }) => {
        seen = new URL(request.url);
        return HttpResponse.json({
          audit_log: [auditEntryFixture()],
          pagination: { limit: 50, offset: 0, total: 1, has_more: false },
        });
      }),
    );
    renderPage();
    await screen.findByText("plan.read");
    await userEvent.type(screen.getByLabelText("Дія"), "user.update");
    await waitFor(() => expect(seen?.searchParams.get("action")).toBe("user.update"));
  });

  it("«Деталі» показують було/стало як текст і згортаються", async () => {
    renderPage();
    const row = await screen.findByRole("row", { name: /user\.update/ });
    const toggle = within(row).getByRole("button", { name: "Деталі" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    const details = await screen.findByRole("region", { name: "Деталі запису 9003" });
    expect(within(details).getByText(/"role": "student"/)).toBeInTheDocument();
    expect(within(details).getByText(/"role": "admin"/)).toBeInTheDocument();
    await userEvent.click(toggle);
    expect(screen.queryByRole("region", { name: "Деталі запису 9003" })).not.toBeInTheDocument();
  });

  it("HTML у значеннях лишається текстом", async () => {
    renderPage();
    const row = await screen.findByRole("row", { name: /plan\.update/ });
    await userEvent.click(within(row).getByRole("button", { name: "Деталі" }));
    const details = await screen.findByRole("region", { name: "Деталі запису 9004" });
    expect(within(details).getByText(/<img src=x onerror=alert\(1\)>/)).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("помилка завантаження деталей показує повідомлення", async () => {
    server.use(
      http.get("*/api/v1/admin/audit-log/:id", () =>
        HttpResponse.json({ code: "AUDIT_ENTRY_NOT_FOUND", message: "x", details: [] }, { status: 404 }),
      ),
    );
    renderPage();
    const row = await screen.findByRole("row", { name: /user\.update/ });
    await userEvent.click(within(row).getByRole("button", { name: "Деталі" }));
    expect(await screen.findByText("Не вдалося завантажити деталі")).toBeInTheDocument();
  });

  it("порожній журнал: «Записів немає»", async () => {
    db.admin.auditLog = [];
    renderPage();
    expect(await screen.findByText("Записів немає")).toBeInTheDocument();
  });
});
