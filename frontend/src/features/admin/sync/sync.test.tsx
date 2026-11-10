// Використання ШІ: Codex перевірив режими імпорту та віддаленого входу. Перевірка: Vitest.
// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setAccessToken } from "../../../api/token";
import { db } from "../../../mocks/db";
import { server } from "../../../mocks/server";
import { configFixture, configHandler, syncJobFixture } from "../../../test/handlers";
import { SyncPage } from "./SyncPage";
import { syncStatusLabel } from "./useSync";

function renderSync(pollMs?: number) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <SyncPage pollMs={pollMs} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  setAccessToken("t");
  server.use(configHandler());
});

describe("syncStatusLabel", () => {
  it("називає статуси українською", () => {
    expect(syncStatusLabel("queued")).toBe("У черзі");
    expect(syncStatusLabel("running")).toBe("Виконується");
    expect(syncStatusLabel("succeeded")).toBe("Успішно");
    expect(syncStatusLabel("failed")).toBe("Помилка");
  });
});

describe("SyncPage", () => {
  it("імпортує JSON, коли серверний парсинг вимкнений", async () => {
    server.use(configHandler({
      features: { ...configFixture().features, saz_catalog_live: false },
    }));
    server.use(http.post("*/api/v1/admin/sync-jobs/saz-import", async ({ request }) => {
      expect(await request.json()).toEqual({ version: 1 });
      db.admin.syncJobs = [syncJobFixture({ status: "succeeded", added_count: 1 })];
      return HttpResponse.json(db.admin.syncJobs[0], { status: 201 });
    }));
    db.admin.syncJobs = [];
    renderSync();
    await screen.findByText("Запусків ще не було");
    expect(screen.queryByRole("button", { name: "Запустити парсинг" })).not.toBeInTheDocument();
    await userEvent.upload(
      await screen.findByLabelText("Файл каталогу САЗ"),
      new File(['{"version":1}'], "saz_export.json", { type: "application/json" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Імпортувати каталог" }));
    expect(await screen.findByText("Успішно")).toBeInTheDocument();
  });

  it("вимагає сесію перед серверним парсингом у режимі віддаленого входу", async () => {
    server.use(configHandler({
      features: { ...configFixture().features, saz_catalog_live: true, saz_remote_login: true },
    }));
    server.use(
      http.get("*/api/v1/admin/saz-session", () => HttpResponse.json({ connected: false })),
      http.post("*/api/v1/admin/saz-session/login", () => HttpResponse.json({ id: "test-id" }, { status: 201 })),
      http.get("*/api/v1/admin/saz-session/login/test-id/frame", () =>
        new HttpResponse(null, {
          status: 409,
          headers: { "Content-Type": "application/json" },
        }),
      ),
      http.delete("*/api/v1/admin/saz-session/login/test-id", () => new HttpResponse(null, { status: 204 })),
    );

    renderSync();
    expect(await screen.findByRole("button", { name: "Запустити парсинг" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Імпортувати каталог" })).not.toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: "Підключити САЗ" }));
    expect(await screen.findByRole("button", { name: "Перевірити й зберегти сесію" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Скасувати" }));
    expect(await screen.findByRole("button", { name: "Підключити САЗ" })).toBeInTheDocument();
  });

  it("показує журнал: джерело, статус, лічильники й повідомлення про помилку", async () => {
    db.admin.syncJobs = [
      syncJobFixture({
        id: 2,
        status: "failed",
        error_message: "Не вдалося знайти таблицю дисциплін",
      }),
      syncJobFixture({ id: 1, status: "succeeded", added_count: 12, updated_count: 3 }),
    ];
    renderSync();
    const failed = await screen.findByRole("row", { name: /Не вдалося знайти таблицю дисциплін/ });
    expect(within(failed).getByText("Помилка")).toBeInTheDocument();
    const ok = screen.getByRole("row", { name: /Успішно/ });
    expect(within(ok).getByText("12")).toBeInTheDocument();
    expect(within(ok).getByText("3")).toBeInTheDocument();
    expect(within(ok).getByText("Каталог САЗ")).toBeInTheDocument();
  });

  it("порожній журнал: «Запусків ще не було»", async () => {
    db.admin.syncJobs = [];
    renderSync();
    expect(await screen.findByText("Запусків ще не було")).toBeInTheDocument();
  });

  it("«Запустити парсинг» додає запис «У черзі»", async () => {
    db.admin.syncJobs = [];
    renderSync();
    const start = await screen.findByRole("button", { name: "Запустити парсинг" });
    expect(screen.queryByLabelText("Файл каталогу САЗ")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Імпортувати каталог" })).not.toBeInTheDocument();
    await userEvent.click(start);
    const row = await screen.findByRole("row", { name: /У черзі/ });
    expect(within(row).getByText("Каталог САЗ")).toBeInTheDocument();
  });

  it("поки є запис у черзі, список опитується й показує «Успішно»", async () => {
    db.admin.syncJobs = [syncJobFixture({ id: 5, status: "queued", finished_at: null })];
    renderSync(20);
    expect(await screen.findByText("У черзі")).toBeInTheDocument();
    expect(await screen.findByText("Успішно", {}, { timeout: 3000 })).toBeInTheDocument();
  });

  it("409 SYNC_JOB_ALREADY_RUNNING пояснює, що парсинг уже триває; кнопка знову активна", async () => {
    server.use(
      http.post("*/api/v1/admin/sync-jobs", () =>
        HttpResponse.json(
          { code: "SYNC_JOB_ALREADY_RUNNING", message: "running", details: [] },
          { status: 409 },
        ),
      ),
    );
    db.admin.syncJobs = [];
    renderSync();
    await screen.findByText("Запусків ще не було");
    await userEvent.click(screen.getByRole("button", { name: "Запустити парсинг" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Парсинг цього джерела вже виконується",
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Запустити парсинг" })).toBeEnabled(),
    );
  });

  it("сертифікатні програми доступні у виборі джерела лише за feature-флагом", async () => {
    db.admin.syncJobs = [];
    renderSync();
    await screen.findByText("Запусків ще не було");
    expect(screen.queryByRole("option", { name: "Сертифікатні програми" })).not.toBeInTheDocument();
  });

  it("з увімкненим флагом можна обрати сертифікатні програми", async () => {
    server.use(
      configHandler({ features: { ...configFixture().features, certificate_programs: true } }),
    );
    db.admin.syncJobs = [];
    renderSync();
    expect(
      await screen.findByRole("option", { name: "Сертифікатні програми" }),
    ).toBeInTheDocument();
  });
});
