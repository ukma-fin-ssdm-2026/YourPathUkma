// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import type { Discipline } from "../../api/types";
import { server } from "../../mocks/server";
import { directionsHandler, disciplineFixture, disciplinesHandler } from "../../test/handlers";
import { CatalogPanel } from "./CatalogPanel";
import type { BuilderPlan } from "./plan";

const emptyPlan = (items: BuilderPlan["items"] = []): BuilderPlan => ({
  academic_year: 2026,
  course: 3,
  load_levels: { autumn: "medium", spring: "medium", summer: "medium" },
  items,
});

const pro = disciplineFixture({
  id: 101,
  title: "Машинне навчання",
  directions: ["Data Science"],
  credits: 6,
});
const free = disciplineFixture({
  id: 102,
  title: "Основи UX",
  directions: [],
  credits: 3,
  instructor: "Лисенко А. Р.",
});

function renderPanel(props: Partial<React.ComponentProps<typeof CatalogPanel>> = {}) {
  const onAdd = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <CatalogPanel
        plan={emptyPlan()}
        studentDirections={["Data Science"]}
        normativeIds={[]}
        takenIds={[]}
        onAdd={onAdd}
        {...props}
      />
    </QueryClientProvider>,
  );
  return onAdd;
}

beforeEach(() => {
  server.use(directionsHandler(["Data Science", "Cybersecurity"]));
});

describe("CatalogPanel: рядки", () => {
  it("показує назву, викладача, кредити й тег за напрямками студента", async () => {
    server.use(disciplinesHandler([pro, free]));
    renderPanel();
    expect(await screen.findByText("Машинне навчання")).toBeInTheDocument();
    expect(screen.getByText("Лисенко А. Р.", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("профорієнтовна")).toBeInTheDocument();
    expect(screen.getByText("вільний вибір")).toBeInTheDocument();
  });

  it("тег залежить від напрямків студента", async () => {
    server.use(disciplinesHandler([pro]));
    renderPanel({ studentDirections: ["Cybersecurity"] });
    expect(await screen.findByText("вільний вибір")).toBeInTheDocument();
  });

  it("«+» віддає дисципліну в onAdd", async () => {
    server.use(disciplinesHandler([pro]));
    const onAdd = renderPanel();
    await userEvent.click(await screen.findByRole("button", { name: "Додати Машинне навчання" }));
    expect(onAdd).toHaveBeenCalledWith(expect.objectContaining({ id: 101 }));
  });
});

describe("CatalogPanel: недоступні дисципліни", () => {
  const cases: [string, Partial<React.ComponentProps<typeof CatalogPanel>>, string][] = [
    [
      "вже в плані",
      {
        plan: emptyPlan([
          { course_id: 101, title: "x", trimester: 1, credits: 6, is_free_elective: false },
        ]),
      },
      "Вже в плані",
    ],
    ["нормативна від деканату", { normativeIds: [101] }, "Додав деканат"],
    ["вже пройдена", { takenIds: [101] }, "Вже пройдено"],
  ];
  it.each(cases)("%s: кнопка вимкнена з поясненням", async (_name, props, reason) => {
    server.use(disciplinesHandler([pro]));
    const onAdd = renderPanel(props);
    const button = await screen.findByRole("button", { name: "Додати Машинне навчання" });
    expect(button).toBeDisabled();
    expect(screen.getByText(reason)).toBeInTheDocument();
    await userEvent.click(button);
    expect(onAdd).not.toHaveBeenCalled();
  });
});

describe("CatalogPanel: фільтри", () => {
  const lastUrl = (urls: URL[]) => urls.at(-1)!.searchParams;

  it("завжди просить лише вибіркові, а «Осінь» додає trimester=1", async () => {
    const urls: URL[] = [];
    server.use(disciplinesHandler([pro], { onRequest: (u) => urls.push(u) }));
    renderPanel();
    await screen.findByText("Машинне навчання");
    expect(lastUrl(urls).get("discipline_type")).toBe("elective");
    await userEvent.click(screen.getByRole("button", { name: "Осінь" }));
    await waitFor(() => expect(lastUrl(urls).get("trimester")).toBe("1"));
  });

  it("напрямок із select іде в запит", async () => {
    const urls: URL[] = [];
    server.use(disciplinesHandler([pro], { onRequest: (u) => urls.push(u) }));
    renderPanel();
    await screen.findByText("Машинне навчання");
    await userEvent.selectOptions(await screen.findByLabelText("Напрямок"), "Cybersecurity");
    await waitFor(() => expect(lastUrl(urls).get("direction")).toBe("Cybersecurity"));
  });

  it("викладач шукається лише після паузи", async () => {
    const urls: URL[] = [];
    server.use(disciplinesHandler([pro], { onRequest: (u) => urls.push(u) }));
    renderPanel();
    await screen.findByText("Машинне навчання");
    await userEvent.type(screen.getByLabelText("Викладач"), "Пет");
    await waitFor(() => expect(lastUrl(urls).get("instructor")).toBe("Пет"), { timeout: 3000 });
    expect(urls.filter((u) => u.searchParams.has("instructor"))).toHaveLength(1);
  });
});

describe("CatalogPanel: стани", () => {
  it("порожній результат", async () => {
    server.use(disciplinesHandler([], { total: 0 }));
    renderPanel();
    expect(await screen.findByText("Нічого не знайдено")).toBeInTheDocument();
  });

  it("помилка сервера показує повідомлення", async () => {
    server.use(
      http.get("*/api/v1/disciplines", () =>
        HttpResponse.json(
          { code: "INTERNAL_ERROR", message: "Внутрішня помилка сервера", details: [] },
          { status: 500 },
        ),
      ),
    );
    renderPanel();
    expect(await screen.findByRole("alert")).toHaveTextContent("Внутрішня помилка сервера");
  });

  it("на останній сторінці «Далі» недоступна", async () => {
    server.use(disciplinesHandler([pro, free], { total: 2 }));
    renderPanel();
    await screen.findByText("Машинне навчання");
    expect(screen.getByRole("button", { name: "Далі" })).toBeDisabled();
  });

  it("під час завантаження показує skeleton", () => {
    server.use(disciplinesHandler([pro] as Discipline[]));
    renderPanel();
    expect(screen.getByLabelText("Завантажуємо каталог")).toBeInTheDocument();
  });
});
