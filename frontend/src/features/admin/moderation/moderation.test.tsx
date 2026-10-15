// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setAccessToken } from "../../../api/token";
import { db } from "../../../mocks/db";
import { server } from "../../../mocks/server";
import { ModerationPage } from "./ModerationPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ModerationPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => setAccessToken("t"));

const card = (id: number) => screen.getByRole("group", { name: `Запис ${id}` });

describe("ModerationPage", () => {
  it("показує картки черги: тип зміни й рядки diff/payload", async () => {
    renderPage();
    const update = await screen.findByRole("group", { name: "Запис 501" });
    expect(within(update).getByText("Зміна")).toBeInTheDocument();
    expect(within(update).getByText("credits: 5 → 4")).toBeInTheDocument();
    expect(within(card(503)).getByText("Додавання")).toBeInTheDocument();
    expect(within(card(503)).getByText("title: Машинне навчання")).toBeInTheDocument();
    expect(within(card(505)).getByText("Видалення")).toBeInTheDocument();
  });

  it("HTML у значенні лишається текстом і переноситься", async () => {
    db.admin.moderationItems[0]!.diff = { title: { old: "а", new: "<img src=x onerror=alert(1)>" } };
    renderPage();
    const line = await screen.findByText("title: а → <img src=x onerror=alert(1)>");
    expect(line).toHaveClass("break-words");
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("«Схвалити» на картці прибирає запис із черги", async () => {
    renderPage();
    await screen.findByRole("group", { name: "Запис 501" });
    await userEvent.click(within(card(501)).getByRole("button", { name: "Схвалити" }));
    await waitFor(() => expect(screen.queryByRole("group", { name: "Запис 501" })).not.toBeInTheDocument());
    expect(db.admin.moderationItems.find((i) => i.id === 501)?.status).toBe("approved");
  });

  it("«Відхилити» просить причину й надсилає її", async () => {
    const bodies: string[] = [];
    server.use(
      http.post("*/api/v1/admin/moderation-items/:id/reject", async ({ request }) => {
        bodies.push(await request.text());
        db.admin.moderationItems[0]!.status = "rejected";
        return HttpResponse.json(db.admin.moderationItems[0]);
      }),
    );
    renderPage();
    await screen.findByRole("group", { name: "Запис 501" });
    await userEvent.click(within(card(501)).getByRole("button", { name: "Відхилити" }));
    await userEvent.type(within(card(501)).getByLabelText("Причина (необов'язково)"), "Хибний парсинг");
    await userEvent.click(within(card(501)).getByRole("button", { name: "Підтвердити відхилення" }));
    await waitFor(() => expect(bodies).toEqual(['{"reason":"Хибний парсинг"}']));
    await waitFor(() => expect(screen.queryByRole("group", { name: "Запис 501" })).not.toBeInTheDocument());
  });

  it("вибір карток вмикає масові дії; «Вибрати всі» відмічає сторінку", async () => {
    renderPage();
    await screen.findByRole("group", { name: "Запис 501" });
    expect(screen.queryByRole("button", { name: /Схвалити вибрані/ })).not.toBeInTheDocument();
    await userEvent.click(within(card(501)).getByRole("checkbox"));
    await userEvent.click(within(card(502)).getByRole("checkbox"));
    expect(screen.getByRole("button", { name: "Схвалити вибрані (2)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Відхилити вибрані (2)" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: "Вибрати всі" }));
    expect(screen.getByRole("button", { name: "Схвалити вибрані (5)" })).toBeInTheDocument();
  });

  it("масове схвалення з пропущеними показує підсумок і причину", async () => {
    server.use(
      http.post("*/api/v1/admin/moderation-items/bulk-review", () =>
        HttpResponse.json({
          approved: [501],
          rejected: [],
          skipped: [{ id: 503, code: "MODERATION_ITEM_ALREADY_REVIEWED" }],
        }),
      ),
    );
    renderPage();
    await screen.findByRole("group", { name: "Запис 501" });
    await userEvent.click(within(card(501)).getByRole("checkbox"));
    await userEvent.click(within(card(503)).getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: "Схвалити вибрані (2)" }));
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent("Схвалено 1, пропущено 1");
    expect(status).toHaveTextContent("Запис #503 пропущено: уже розглянуто");
    expect(screen.queryByRole("button", { name: /Схвалити вибрані/ })).not.toBeInTheDocument();
  });

  it("409 на картці: «Запис уже розглянуто», картка зникає після оновлення", async () => {
    server.use(
      http.post("*/api/v1/admin/moderation-items/:id/approve", () => {
        db.admin.moderationItems[0]!.status = "approved";
        return HttpResponse.json(
          { code: "MODERATION_ITEM_ALREADY_REVIEWED", message: "x", details: [] },
          { status: 409 },
        );
      }),
    );
    renderPage();
    await screen.findByRole("group", { name: "Запис 501" });
    await userEvent.click(within(card(501)).getByRole("button", { name: "Схвалити" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Запис уже розглянуто");
    await waitFor(() => expect(screen.queryByRole("group", { name: "Запис 501" })).not.toBeInTheDocument());
  });

  it("порожня черга: «Черга порожня»", async () => {
    db.admin.moderationItems = [];
    renderPage();
    expect(await screen.findByText("Черга порожня")).toBeInTheDocument();
  });

  it("вкладка «Схвалені» показує розглянуті записи без чекбоксів", async () => {
    db.admin.moderationItems[0]!.status = "approved";
    db.admin.moderationItems[0]!.reviewed_by = { id: 1, full_name: "Адміністратор" };
    renderPage();
    await screen.findByRole("group", { name: "Запис 502" });
    await userEvent.click(screen.getByRole("button", { name: "Схвалені" }));
    const approved = await screen.findByRole("group", { name: "Запис 501" });
    expect(within(approved).queryByRole("checkbox")).not.toBeInTheDocument();
    expect(within(approved).queryByRole("button", { name: "Схвалити" })).not.toBeInTheDocument();
    expect(within(approved).getByText(/Розглянув: Адміністратор/)).toBeInTheDocument();
  });

  it("фільтр типу «Додавання» залишає лише додавання", async () => {
    renderPage();
    await screen.findByRole("group", { name: "Запис 501" });
    await userEvent.click(screen.getByRole("button", { name: "Додавання" }));
    await waitFor(() => expect(screen.getAllByRole("group", { name: /^Запис / })).toHaveLength(2));
    expect(screen.queryByRole("group", { name: "Запис 501" })).not.toBeInTheDocument();
  });
});

describe("ModerationPage: пагінація", () => {
  it("після розгляду останнього запису сторінки повертає на попередню, а не показує «Черга порожня»", async () => {
    db.admin.moderationItems = Array.from({ length: 21 }, (_, index) => ({
      ...db.admin.moderationItems[0]!,
      id: 600 + index,
      course_id: 100 + index,
      payload: { title: `Дисципліна ${index + 1}` },
      diff: null,
      change_type: "add" as const,
    }));
    renderPage();
    await screen.findByRole("group", { name: "Запис 600" });
    await userEvent.click(screen.getByRole("button", { name: "Далі" }));
    const last = await screen.findByRole("group", { name: "Запис 620" });
    await userEvent.click(within(last).getByRole("button", { name: "Схвалити" }));
    expect(await screen.findByRole("group", { name: "Запис 600" })).toBeInTheDocument();
    expect(screen.queryByText("Черга порожня")).not.toBeInTheDocument();
    expect(screen.getByText("Сторінка 1 з 1")).toBeInTheDocument();
  });
});
