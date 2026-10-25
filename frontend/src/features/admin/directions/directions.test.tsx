// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setAccessToken } from "../../../api/token";
import { db } from "../../../mocks/db";
import { server } from "../../../mocks/server";
import { DirectionsPage } from "./DirectionsPage";

function renderPage() {
  // GET /directions — це ✅-ендпоінт реального бекенду, у тестах читає стан із db.
  server.use(
    http.get("*/api/v1/directions", () => HttpResponse.json({ directions: db.admin.directions })),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <DirectionsPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => setAccessToken("t"));

const item = (name: string) => screen.getByRole("listitem", { name });

describe("DirectionsPage", () => {
  it("показує напрямки з описами", async () => {
    renderPage();
    const science = await screen.findByRole("listitem", { name: "Data Science" });
    expect(within(science).getByText("Дані та ML")).toBeInTheDocument();
    expect(item("Веброзробка")).toBeInTheDocument();
  });

  it("додає напрямок: надсилає назву й опис, новий напрямок з'являється у списку", async () => {
    const bodies: string[] = [];
    renderPage();
    server.use(
      http.post("*/api/v1/admin/directions", async ({ request }) => {
        const text = await request.text();
        bodies.push(text);
        const body = JSON.parse(text) as { name: string; description?: string };
        const created = { id: 9, name: body.name, description: body.description ?? null };
        db.admin.directions.push(created);
        return HttpResponse.json(created, { status: 201 });
      }),
    );
    await screen.findByText("Data Science");
    await userEvent.click(screen.getByRole("button", { name: "Додати напрямок" }));
    await userEvent.type(screen.getByLabelText("Назва"), "Робототехніка");
    await userEvent.type(screen.getByLabelText("Опис"), "Роботи й керування");
    await userEvent.click(screen.getByRole("button", { name: "Зберегти" }));
    expect(await screen.findByRole("listitem", { name: "Робототехніка" })).toBeInTheDocument();
    expect(bodies).toEqual(['{"name":"Робототехніка","description":"Роботи й керування"}']);
    expect(screen.queryByLabelText("Назва")).not.toBeInTheDocument();
  });

  it("редагування надсилає лише змінені поля", async () => {
    const bodies: string[] = [];
    renderPage();
    server.use(
      http.patch("*/api/v1/admin/directions/:id", async ({ request }) => {
        bodies.push(await request.text());
        return HttpResponse.json({ id: 1, name: "Data Science", description: "Нове" });
      }),
    );
    await screen.findByText("Data Science");
    await userEvent.click(within(item("Data Science")).getByRole("button", { name: "Редагувати" }));
    const description = screen.getByLabelText("Опис");
    await userEvent.clear(description);
    await userEvent.type(description, "Нове");
    await userEvent.click(screen.getByRole("button", { name: "Зберегти" }));
    await waitFor(() => expect(bodies).toEqual(['{"description":"Нове"}']));
  });

  it("409 DIRECTION_NAME_TAKEN: пояснення біля назви, форма лишається", async () => {
    renderPage();
    await screen.findByText("Data Science");
    await userEvent.click(screen.getByRole("button", { name: "Додати напрямок" }));
    await userEvent.type(screen.getByLabelText("Назва"), "data science");
    await userEvent.click(screen.getByRole("button", { name: "Зберегти" }));
    expect(await screen.findByText("Напрямок із такою назвою вже існує")).toBeInTheDocument();
    expect(screen.getByLabelText("Назва")).toHaveValue("data science");
  });

  it("надто коротка назва блокується до запиту", async () => {
    const bodies: string[] = [];
    renderPage();
    server.use(
      http.post("*/api/v1/admin/directions", async ({ request }) => {
        bodies.push(await request.text());
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    await screen.findByText("Data Science");
    await userEvent.click(screen.getByRole("button", { name: "Додати напрямок" }));
    await userEvent.type(screen.getByLabelText("Назва"), "А");
    await userEvent.click(screen.getByRole("button", { name: "Зберегти" }));
    expect(screen.getByText("Від 2 до 50 символів")).toBeInTheDocument();
    expect(bodies).toEqual([]);
  });

  it("видалення просить підтвердження й прибирає напрямок", async () => {
    renderPage();
    await screen.findByText("Веброзробка");
    await userEvent.click(within(item("Веброзробка")).getByRole("button", { name: "Видалити" }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("Веброзробка");
    await userEvent.click(within(dialog).getByRole("button", { name: "Видалити" }));
    await waitFor(() =>
      expect(screen.queryByRole("listitem", { name: "Веброзробка" })).not.toBeInTheDocument(),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("«Скасувати» у підтвердженні лишає напрямок", async () => {
    renderPage();
    await screen.findByText("Веброзробка");
    await userEvent.click(within(item("Веброзробка")).getByRole("button", { name: "Видалити" }));
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Скасувати" }),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(item("Веброзробка")).toBeInTheDocument();
  });

  it("409 DIRECTION_IN_USE: напрямок лишається, пояснено, що спершу відв'язати", async () => {
    renderPage();
    await screen.findByText("Кібербезпека");
    await userEvent.click(within(item("Кібербезпека")).getByRole("button", { name: "Видалити" }));
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Видалити" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Напрямок використовується; спершу відв'яжіть його",
    );
    expect(item("Кібербезпека")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
