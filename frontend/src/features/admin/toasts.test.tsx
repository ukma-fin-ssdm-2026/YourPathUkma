// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import type { ReactElement } from "react";
import { toast } from "sonner";
import { setAccessToken } from "../../api/token";
import { db } from "../../mocks/db";
import { server } from "../../mocks/server";
import { configHandler } from "../../test/handlers";
import { DirectionsPage } from "./directions/DirectionsPage";
import { ModerationPage } from "./moderation/ModerationPage";
import { SyncPage } from "./sync/SyncPage";
import { UsersPage } from "./users/UsersPage";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

function renderPage(page: ReactElement) {
  server.use(
    configHandler(),
    http.get("*/api/v1/directions", () => HttpResponse.json({ directions: db.admin.directions })),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}>{page}</QueryClientProvider>);
}

const conflict = (code: string) =>
  HttpResponse.json({ code, message: "x", details: [] }, { status: 409 });

beforeEach(() => {
  setAccessToken("t");
  vi.mocked(toast.success).mockClear();
});

describe("тости успіху в адмінці", () => {
  it("запуск парсингу", async () => {
    db.admin.syncJobs = [];
    renderPage(<SyncPage />);
    await screen.findByText("Запусків ще не було");
    await userEvent.click(screen.getByRole("button", { name: "Запустити парсинг" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Парсинг запущено"));
  });

  it("409 при запуску парсингу тосту не дає", async () => {
    server.use(http.post("*/api/v1/admin/sync-jobs", () => conflict("SYNC_JOB_ALREADY_RUNNING")));
    db.admin.syncJobs = [];
    renderPage(<SyncPage />);
    await screen.findByText("Запусків ще не було");
    await userEvent.click(screen.getByRole("button", { name: "Запустити парсинг" }));
    await screen.findByRole("alert");
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("схвалення й відхилення запису", async () => {
    renderPage(<ModerationPage />);
    const first = await screen.findByRole("group", { name: "Запис 501" });
    await userEvent.click(within(first).getByRole("button", { name: "Схвалити" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Запис схвалено"));
    const second = await screen.findByRole("group", { name: "Запис 502" });
    await userEvent.click(within(second).getByRole("button", { name: "Відхилити" }));
    await userEvent.click(within(second).getByRole("button", { name: "Підтвердити відхилення" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Запис відхилено"));
  });

  it("409 при розгляді запису тосту не дає", async () => {
    server.use(
      http.post("*/api/v1/admin/moderation-items/:id/approve", () =>
        conflict("MODERATION_ITEM_ALREADY_REVIEWED"),
      ),
    );
    renderPage(<ModerationPage />);
    const first = await screen.findByRole("group", { name: "Запис 501" });
    await userEvent.click(within(first).getByRole("button", { name: "Схвалити" }));
    await screen.findByRole("alert");
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("збереження користувача", async () => {
    renderPage(<UsersPage />);
    const row = await screen.findByRole("row", { name: /Владислав/ });
    await userEvent.click(within(row).getByRole("button", { name: "Змінити" }));
    await userEvent.selectOptions(screen.getByLabelText("Курс"), "4");
    await userEvent.click(screen.getByRole("button", { name: "Зберегти" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Зміни збережено"));
  });

  it("збереження й видалення напрямку", async () => {
    renderPage(<DirectionsPage />);
    await screen.findByText("Data Science");
    await userEvent.click(screen.getByRole("button", { name: "Додати напрямок" }));
    await userEvent.type(screen.getByLabelText("Назва"), "Робототехніка");
    await userEvent.click(screen.getByRole("button", { name: "Зберегти" }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Напрямок збережено"));
    const item = await screen.findByRole("listitem", { name: "Веброзробка" });
    await userEvent.click(within(item).getByRole("button", { name: "Видалити" }));
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Видалити" }),
    );
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Напрямок видалено"));
  });

  it("DIRECTION_IN_USE тосту не дає", async () => {
    renderPage(<DirectionsPage />);
    const item = await screen.findByRole("listitem", { name: "Кібербезпека" });
    await userEvent.click(within(item).getByRole("button", { name: "Видалити" }));
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Видалити" }),
    );
    await screen.findByRole("alert");
    expect(toast.success).not.toHaveBeenCalled();
  });
});
