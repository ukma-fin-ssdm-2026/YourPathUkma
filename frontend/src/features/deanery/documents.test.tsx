// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider, createMemoryRouter } from "react-router";
import type { DeaneryDocument } from "../../api/types";
import { setAccessToken } from "../../api/token";
import { formatBytes } from "../../lib/bytes";
import { db } from "../../mocks/db";
import { normativeCourses } from "../../mocks/fixtures";
import { server } from "../../mocks/server";
import { configHandler } from "../../test/handlers";
import { DeaneryPage } from "./DeaneryPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(
    [{ path: "/path/create/document", element: <DeaneryPage pollMs={20} /> }],
    { initialEntries: ["/path/create/document?year=2026"] },
  );
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

const user = () => userEvent.setup({ applyAccept: false });
const upload = async (name: string) =>
  user().upload(
    screen.getByLabelText("Файл документа деканату"),
    new File(["вміст"], name, { type: "application/pdf" }),
  );

function parsedDoc(overrides: Partial<DeaneryDocument> = {}): DeaneryDocument {
  return {
    id: 7,
    academic_year: 2026,
    original_filename: "ready.pdf",
    mime_type: "pdf",
    size_bytes: 184233,
    parse_status: "parsed",
    parse_error: null,
    uploaded_at: "2026-10-08T10:00:00Z",
    normative_courses: normativeCourses(),
    ...overrides,
  };
}

beforeEach(() => {
  setAccessToken("t");
  server.use(configHandler());
});

describe("formatBytes", () => {
  it("КБ для малих файлів і МБ з комою для великих", () => {
    expect(formatBytes(184233)).toBe("180 КБ");
    expect(formatBytes(2516582)).toBe("2,4 МБ");
  });
});

describe("стани документа", () => {
  it("pending → parsed: статус змінюється, з'являються нормативні й підсумок", async () => {
    renderPage();
    await upload("plan_2026.pdf");
    expect(await screen.findByText("Розпізнаємо…")).toBeInTheDocument();
    expect(await screen.findByText("Розпізнано", {}, { timeout: 3000 })).toBeInTheDocument();
    const panel = screen.getByRole("region", { name: "Розпізнані нормативні" });
    // Список оновлюється одразу після картки, тож панель наповнюється з невеликою затримкою.
    for (const title of [
      "Архітектура ПЗ",
      "Проєктний практикум",
      "Виробнича практика",
      "Фізичне виховання",
    ]) {
      expect(await within(panel).findByText(title)).toBeInTheDocument();
    }
    expect(within(panel).getByText("Разом").parentElement).toHaveTextContent("29");
    expect(within(panel).getByText(/немає в каталозі/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Далі: до побажань" })).toHaveAttribute(
      "href",
      "/path/create/preferences?year=2026",
    );
  });

  it("failed показує причину, «Далі» недоступна", async () => {
    renderPage();
    await upload("scan.pdf");
    expect(await screen.findByText("Не розпізнано", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByText("Не вдалося прочитати таблицю дисциплін")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Далі: до побажань" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Далі: до побажань" })).toBeDisabled();
  });

  it("раніше завантажений розпізнаний документ показується одразу", async () => {
    db.documents.push(parsedDoc());
    renderPage();
    expect(await screen.findByText("ready.pdf")).toBeInTheDocument();
    expect(screen.getByText("180 КБ")).toBeInTheDocument();
    expect(await screen.findByText("Фізичне виховання")).toBeInTheDocument();
  });

  it("без документів панель підказує, що буде після розпізнавання", () => {
    renderPage();
    expect(screen.getByText(/Після розпізнавання тут з'являться нормативні/)).toBeInTheDocument();
  });
});

describe("видалення документа", () => {
  const openDialog = async () => {
    const card = await screen.findByTestId("doc-7");
    await userEvent.click(within(card).getByRole("button", { name: "Видалити" }));
    return screen.getByRole("dialog");
  };

  it("підтвердження прибирає картку", async () => {
    db.documents.push(parsedDoc());
    renderPage();
    const dialog = await openDialog();
    await userEvent.click(within(dialog).getByRole("button", { name: "Видалити" }));
    await waitFor(() => expect(screen.queryByTestId("doc-7")).not.toBeInTheDocument());
    expect(screen.getByText(/Після розпізнавання тут з'являться нормативні/)).toBeInTheDocument();
  });

  it("документ у плані (409) лишається з поясненням", async () => {
    db.documents.push(parsedDoc({ original_filename: "inuse.pdf" }));
    renderPage();
    const dialog = await openDialog();
    await userEvent.click(within(dialog).getByRole("button", { name: "Видалити" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Документ використовується в плані, який уже подано",
    );
    expect(screen.getByTestId("doc-7")).toBeInTheDocument();
  });

  it("скасування не видаляє", async () => {
    db.documents.push(parsedDoc());
    renderPage();
    const dialog = await openDialog();
    await userEvent.click(within(dialog).getByRole("button", { name: "Скасувати" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(db.documents).toHaveLength(1);
  });
});
