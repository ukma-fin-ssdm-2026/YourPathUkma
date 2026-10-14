// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, delay } from "msw";
import { RouterProvider, createMemoryRouter } from "react-router";
import { setAccessToken } from "../../api/token";
import { db } from "../../mocks/db";
import { server } from "../../mocks/server";
import { configHandler } from "../../test/handlers";
import { DeaneryPage } from "./DeaneryPage";

const MAX = 10_485_760;

function renderPage(entry = "/path/create/document?year=2026") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(
    [
      { path: "/path/create/document", element: <DeaneryPage /> },
      { path: "/path/create", element: <p>конструктор</p> },
    ],
    { initialEntries: [entry] },
  );
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

const user = () => userEvent.setup({ applyAccept: false });
const pdf = (name = "plan_2026.pdf") => new File(["вміст"], name, { type: "application/pdf" });
const fileInput = () => screen.getByLabelText("Файл документа деканату");

beforeEach(() => {
  setAccessToken("t");
  server.use(configHandler());
});

describe("DeaneryPage: завантаження", () => {
  it("вибраний PDF завантажується й показує повідомлення про розпізнавання", async () => {
    renderPage();
    await user().upload(fileInput(), pdf());
    expect(await screen.findByText("Завантажено, розпізнаємо…")).toBeInTheDocument();
    expect(db.documents).toHaveLength(1);
    expect(db.documents[0]).toMatchObject({ original_filename: "plan_2026.pdf", academic_year: 2026 });
  });

  it("невідомий тип показує причину й не надсилає запит", async () => {
    renderPage();
    await user().upload(fileInput(), new File(["x"], "notes.txt", { type: "text/plain" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Підтримуються лише PDF і DOCX");
    expect(db.documents).toHaveLength(0);
  });

  it("завеликий файл показує причину й не надсилає запит", async () => {
    renderPage();
    const big = pdf("big.pdf");
    Object.defineProperty(big, "size", { value: MAX + 1 });
    await user().upload(fileInput(), big);
    expect(await screen.findByRole("alert")).toHaveTextContent("Файл завеликий: максимум 10 МБ");
    expect(db.documents).toHaveLength(0);
  });

  it("порожній файл відхиляється на клієнті", async () => {
    renderPage();
    await user().upload(fileInput(), new File([], "empty.pdf", { type: "application/pdf" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Файл порожній");
    expect(db.documents).toHaveLength(0);
  });

  it("перетягування підсвічує зону, а drop завантажує файл", async () => {
    renderPage();
    const zone = screen.getByTestId("dropzone");
    fireEvent.dragEnter(zone);
    expect(zone).toHaveAttribute("data-dragging", "true");
    fireEvent.dragLeave(zone);
    expect(zone).toHaveAttribute("data-dragging", "false");
    fireEvent.drop(zone, { dataTransfer: { files: [pdf("dropped.pdf")] } });
    await waitFor(() => expect(db.documents).toHaveLength(1));
    expect(db.documents[0]!.original_filename).toBe("dropped.pdf");
  });
});

describe("DeaneryPage: помилки сервера", () => {
  it("413 від сервера показується як «Файл завеликий»", async () => {
    renderPage();
    await user().upload(fileInput(), pdf("huge.pdf"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Файл завеликий");
  });

  it("429 показує підказку про ліміт завантажень", async () => {
    server.use(
      http.post("*/api/v1/deanery-documents", () =>
        HttpResponse.json({ code: "RATE_LIMITED", message: "x", details: [] }, { status: 429 }),
      ),
    );
    renderPage();
    await user().upload(fileInput(), pdf());
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Забагато завантажень, спробуйте за кілька хвилин",
    );
  });

  it("інша помилка показує повідомлення сервера й код помилки", async () => {
    server.use(
      http.post("*/api/v1/deanery-documents", () =>
        HttpResponse.json(
          { code: "INTERNAL_ERROR", message: "Внутрішня помилка сервера", details: [] },
          { status: 500, headers: { "X-Request-ID": "rid-9" } },
        ),
      ),
    );
    renderPage();
    await user().upload(fileInput(), pdf());
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Внутрішня помилка сервера");
    expect(alert).toHaveTextContent("Код помилки: rid-9");
  });

  it("поки триває завантаження, кнопка «Обрати файл» недоступна", async () => {
    server.use(
      http.post("*/api/v1/deanery-documents", async () => {
        await delay(150);
        return HttpResponse.json({ id: 1 }, { status: 202 });
      }),
    );
    renderPage();
    await user().upload(fileInput(), pdf());
    expect(screen.getByRole("button", { name: "Обрати файл" })).toBeDisabled();
    await waitFor(() => expect(screen.getByRole("button", { name: "Обрати файл" })).toBeEnabled());
  });
});

describe("DeaneryPage: рік і навігація", () => {
  it("рік береться з ?year=", () => {
    renderPage("/path/create/document?year=2025");
    expect(screen.getByRole("heading", { name: "Документ деканату на 2025/2026" })).toBeInTheDocument();
  });

  it("без ?year= бере поточний рік, обмежений межами /config", async () => {
    renderPage("/path/create/document");
    const year = Math.min(2030, Math.max(2024, new Date().getFullYear()));
    expect(
      await screen.findByRole("heading", { name: `Документ деканату на ${year}/${year + 1}` }),
    ).toBeInTheDocument();
  });

  it("«Пропустити зараз» веде до конструктора", async () => {
    renderPage();
    await userEvent.click(screen.getByRole("link", { name: "Пропустити зараз" }));
    expect(await screen.findByText("конструктор")).toBeInTheDocument();
  });
});
