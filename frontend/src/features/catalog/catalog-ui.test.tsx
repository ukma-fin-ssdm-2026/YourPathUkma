// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { RouterProvider, createMemoryRouter } from "react-router";
import { creditsWord } from "../../lib/credits";
import { server } from "../../mocks/server";
import { configHandler, directionsHandler, disciplineFixture, disciplinesHandler } from "../../test/handlers";
import { CatalogPage } from "./CatalogPage";
import { DisciplineCard } from "./DisciplineCard";

describe("creditsWord", () => {
  it("узгоджує слово «кредит» з числом", () => {
    expect(creditsWord(1)).toBe("кредит");
    expect(creditsWord(3)).toBe("кредити");
    expect(creditsWord(4.5)).toBe("кредита");
    expect(creditsWord(5)).toBe("кредитів");
    expect(creditsWord(21)).toBe("кредит");
    expect(creditsWord(12)).toBe("кредитів");
  });
});

describe("DisciplineCard", () => {
  const reviews = "https://example.ukma.edu.ua/reviews";

  it("показує назву, викладача, курс, триместр і кредити", () => {
    render(<DisciplineCard discipline={disciplineFixture()} reviewsUrl={reviews} />);
    expect(screen.getByRole("heading", { name: "Функціональне програмування" })).toBeInTheDocument();
    expect(screen.getByText(/Петренко І\. М\./)).toBeInTheDocument();
    expect(screen.getByText(/2 курс · Осінь/)).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("кредитів")).toBeInTheDocument();
  });

  it("позначає вільний вибір, коли напрямків немає, інакше показує напрямки", () => {
    const { rerender } = render(<DisciplineCard discipline={disciplineFixture({ directions: [] })} />);
    expect(screen.getByText("вільний вибір")).toBeInTheDocument();
    rerender(<DisciplineCard discipline={disciplineFixture({ directions: ["Data Science", "Cybersecurity"] })} />);
    expect(screen.getByText("Data Science")).toBeInTheDocument();
    expect(screen.getByText("Cybersecurity")).toBeInTheDocument();
    expect(screen.queryByText("вільний вибір")).not.toBeInTheDocument();
  });

  it("посилання на відгуки відкривається в новій вкладці безпечно", () => {
    render(<DisciplineCard discipline={disciplineFixture()} reviewsUrl={reviews} />);
    const link = screen.getByRole("link", { name: /Відгуки/ });
    expect(link).toHaveAttribute("href", reviews);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("опис із HTML показується як текст, а не розмітка", () => {
    const { container } = render(
      <DisciplineCard discipline={disciplineFixture({ description: "<script>alert(1)</script>" })} />,
    );
    expect(screen.getByText("<script>alert(1)</script>")).toBeInTheDocument();
    expect(container.querySelector("script")).toBeNull();
  });

  it("довга назва без пробілів переноситься, порожній опис не ламає картку", () => {
    const longTitle = "Д".repeat(300);
    render(
      <DisciplineCard discipline={disciplineFixture({ title: longTitle, instructor: "П".repeat(120), description: "" })} />,
    );
    expect(screen.getByRole("heading", { name: longTitle })).toHaveClass("break-words");
  });
});

function renderCatalog(entry = "/catalog") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter([{ path: "/catalog", element: <CatalogPage /> }], {
    initialEntries: [entry],
  });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

describe("CatalogPage", () => {
  beforeEach(() => {
    server.use(configHandler(), directionsHandler(["Data Science", "Cybersecurity"]));
  });

  it("під час завантаження показує skeleton", () => {
    server.use(disciplinesHandler([disciplineFixture()]));
    renderCatalog();
    expect(screen.getByLabelText("Завантажуємо каталог")).toBeInTheDocument();
  });

  it("показує картки й кількість дисциплін", async () => {
    server.use(disciplinesHandler([disciplineFixture(), disciplineFixture({ id: 102, title: "Мова Haskell" })], { total: 57 }));
    renderCatalog();
    expect(await screen.findByRole("heading", { name: "Мова Haskell" })).toBeInTheDocument();
    expect(screen.getByText("57 дисциплін")).toBeInTheDocument();
  });

  it("помилка сервера показує повідомлення, код помилки й кнопку повтору", async () => {
    server.use(
      http.get("*/api/v1/disciplines", () =>
        HttpResponse.json(
          { code: "INTERNAL_ERROR", message: "Внутрішня помилка сервера", details: [] },
          { status: 500, headers: { "X-Request-ID": "rid-77" } },
        ),
      ),
    );
    renderCatalog();
    expect(await screen.findByRole("alert")).toHaveTextContent("Внутрішня помилка сервера");
    expect(screen.getByText(/Код помилки: rid-77/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Спробувати ще раз" })).toBeInTheDocument();
  });

  it("порожній результат пропонує скинути фільтри", async () => {
    server.use(disciplinesHandler([], { total: 0 }));
    const router = renderCatalog("/catalog?trimester=2");
    expect(await screen.findByText("Нічого не знайдено")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Скинути фільтри" })[0]!);
    await waitFor(() => expect(router.state.location.search).toBe(""));
  });

  it("клік по «Осінь» додає trimester=1 в адресу й у запит і скидає сторінку", async () => {
    const urls: URL[] = [];
    server.use(disciplinesHandler([disciplineFixture()], { total: 40, onRequest: (u) => urls.push(u) }));
    const router = renderCatalog("/catalog?page=2");
    await screen.findByRole("heading", { name: "Функціональне програмування" });
    await userEvent.click(screen.getByRole("button", { name: "Осінь" }));
    await waitFor(() => expect(router.state.location.search).toBe("?trimester=1"));
    await waitFor(() => expect(urls.at(-1)!.searchParams.get("trimester")).toBe("1"));
    expect(urls.at(-1)!.searchParams.get("offset")).toBe("0");
  });

  it("«Далі» вимкнена на останній сторінці", async () => {
    server.use(disciplinesHandler([disciplineFixture()], { total: 1 }));
    renderCatalog();
    await screen.findByRole("heading", { name: "Функціональне програмування" });
    expect(screen.getByRole("button", { name: "Далі" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Назад" })).toBeDisabled();
  });

  it("сторінка за межами списку показує порожній стан і не падає", async () => {
    server.use(disciplinesHandler([], { total: 30 }));
    renderCatalog("/catalog?page=99");
    expect(await screen.findByText("Нічого не знайдено")).toBeInTheDocument();
  });

  it("поле викладача відправляє запит лише після паузи", async () => {
    const urls: URL[] = [];
    server.use(disciplinesHandler([disciplineFixture()], { onRequest: (u) => urls.push(u) }));
    renderCatalog();
    await screen.findByRole("heading", { name: "Функціональне програмування" });
    await userEvent.type(screen.getByLabelText("Викладач"), "Пет");
    await waitFor(() => expect(urls.at(-1)!.searchParams.get("instructor")).toBe("Пет"), { timeout: 3000 });
    expect(urls.filter((u) => u.searchParams.has("instructor"))).toHaveLength(1);
  });
});
