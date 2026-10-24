// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { RouterProvider, createMemoryRouter } from "react-router";
import { useSession } from "../../auth/session";
import { db } from "../../mocks/db";
import { authResponse } from "../../mocks/fixtures";
import { server } from "../../mocks/server";
import { configHandler, directionsHandler } from "../../test/handlers";
import { PreferencesForm } from "./PreferencesForm";
import { PreferencesPage } from "./PreferencesPage";
import { defaultPreferences } from "./preferences";

const ALL = [
  { id: 7, full_name: "Петренко І. М." },
  { id: 12, full_name: "Гончар В. Т." },
  { id: 21, full_name: "Коваль О. С." },
];

/** Довідник викладачів: пошук за q; без q віддає лише перших двох (21 «невідомий» для словника). */
function instructorsDirectory() {
  return http.get("*/api/v1/instructors", ({ request }) => {
    const q = new URL(request.url).searchParams.get("q");
    const items = q
      ? ALL.filter((i) => i.full_name.toLowerCase().includes(q.toLowerCase()))
      : ALL.slice(0, 2);
    return HttpResponse.json({
      instructors: items,
      pagination: { limit: 10, offset: 0, total: items.length, has_more: false },
    });
  });
}

function renderForm() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <PreferencesForm year={2026} />
    </QueryClientProvider>,
  );
}

function setFreeUsed(used: number) {
  const student = db.me.student!;
  db.me = {
    ...db.me,
    student: {
      ...student,
      course_year: 3,
      onboarding_required: false,
      credits: { ...student.credits, free_choice_used: used },
    },
  };
}

const search = (list: string) => screen.findByLabelText(`Знайти викладача (${list})`);
const section = (title: string) => screen.getByRole("region", { name: title });

beforeEach(() => {
  useSession.getState().setAuthenticated(authResponse());
  server.use(configHandler(), directionsHandler(["Data Science"]), instructorsDirectory());
  setFreeUsed(9);
});

describe("пошук і вибір викладачів", () => {
  it("знаходить викладача після паузи й додає його до бажаних", async () => {
    renderForm();
    await userEvent.type(await search("бажані"), "Пет");
    await userEvent.click(await screen.findByRole("button", { name: "Додати Петренко І. М." }));
    expect(within(section("Бажані викладачі")).getByText("Петренко І. М.")).toBeInTheDocument();
  });

  it("викладач із «Бажаних» не пропонується в «Небажаних»", async () => {
    renderForm();
    await userEvent.type(await search("бажані"), "Пет");
    await userEvent.click(await screen.findByRole("button", { name: "Додати Петренко І. М." }));
    await userEvent.type(await search("небажані"), "Пет");
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Додати Петренко І. М." }),
      ).not.toBeInTheDocument(),
    );
  });

  it("після видалення з «Бажаних» викладача можна додати до «Небажаних»", async () => {
    renderForm();
    await userEvent.type(await search("бажані"), "Пет");
    await userEvent.click(await screen.findByRole("button", { name: "Додати Петренко І. М." }));
    await userEvent.click(screen.getByRole("button", { name: "Прибрати Петренко І. М." }));
    expect(
      screen.queryByRole("button", { name: "Прибрати Петренко І. М." }),
    ).not.toBeInTheDocument();
    await userEvent.type(await search("небажані"), "Пет");
    // «Бажані» теж ще показують пошукову підказку, тож шукаємо кнопку лише в «Небажаних».
    const unwanted = screen.getByRole("region", { name: "Небажані викладачі" });
    await userEvent.click(
      await within(unwanted).findByRole("button", { name: "Додати Петренко І. М." }),
    );
    expect(within(unwanted).getByText("Петренко І. М.")).toBeInTheDocument();
    expect(
      within(section("Бажані викладачі")).queryByRole("button", {
        name: "Прибрати Петренко І. М.",
      }),
    ).not.toBeInTheDocument();
  });

  it("невідомий id показується як «Викладач #id»", async () => {
    db.preferences[2026] = { ...defaultPreferences(2026), preferred_instructor_ids: [99] };
    renderForm();
    expect(await screen.findByText("Викладач #99")).toBeInTheDocument();
  });

  it("збережений id підписується з довідника", async () => {
    db.preferences[2026] = { ...defaultPreferences(2026), unwanted_instructor_ids: [12] };
    renderForm();
    const unwanted = await screen.findByRole("region", { name: "Небажані викладачі" });
    expect(await within(unwanted).findByText("Гончар В. Т.")).toBeInTheDocument();
  });

  it("викладач, доданий пошуком, має ім'я, навіть якщо його немає в словнику", async () => {
    renderForm();
    await userEvent.type(await search("бажані"), "Ков");
    await userEvent.click(await screen.findByRole("button", { name: "Додати Коваль О. С." }));
    expect(within(section("Бажані викладачі")).getByText("Коваль О. С.")).toBeInTheDocument();
    expect(screen.queryByText("Викладач #21")).not.toBeInTheDocument();
  });

  it("менше двох символів не шукає", async () => {
    let calls = 0;
    server.use(
      http.get("*/api/v1/instructors", ({ request }) => {
        if (new URL(request.url).searchParams.has("q")) calls += 1;
        return HttpResponse.json({
          instructors: [],
          pagination: { limit: 10, offset: 0, total: 0, has_more: false },
        });
      }),
    );
    renderForm();
    await userEvent.type(await search("бажані"), "П");
    await new Promise((resolve) => setTimeout(resolve, 450));
    expect(calls).toBe(0);
  });
});

describe("вільний вибір і сертифікат", () => {
  it("перемикач вільного вибору змінює збережене значення, підпис показує залишок", async () => {
    renderForm();
    const toggle = await screen.findByRole("switch", { name: "Дозволити вільний вибір" });
    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText("Лишилось 16 з 25 кредитів на весь час навчання")).toBeInTheDocument();
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "false");
    await userEvent.click(screen.getByRole("button", { name: "Зберегти побажання" }));
    await screen.findByText("Побажання збережено");
    expect(db.preferences[2026]!.include_free_electives).toBe(false);
  });

  it("сертифікат вимкнено з позначкою «незабаром»", async () => {
    renderForm();
    expect(
      await screen.findByRole("switch", { name: "Підібрати сертифікатну програму" }),
    ).toBeDisabled();
    expect(screen.getByText("незабаром")).toBeInTheDocument();
  });

  it("збереження надсилає списки викладачів без перетину", async () => {
    renderForm();
    await userEvent.type(await search("бажані"), "Пет");
    await userEvent.click(await screen.findByRole("button", { name: "Додати Петренко І. М." }));
    await userEvent.type(await search("небажані"), "Гон");
    await userEvent.click(await screen.findByRole("button", { name: "Додати Гончар В. Т." }));
    await userEvent.click(screen.getByRole("button", { name: "Зберегти побажання" }));
    await screen.findByText("Побажання збережено");
    expect(db.preferences[2026]).toMatchObject({
      preferred_instructor_ids: [7],
      unwanted_instructor_ids: [12],
    });
  });
});

describe("PreferencesPage", () => {
  function renderPage(entry: string) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const router = createMemoryRouter(
      [
        { path: "/path/create/preferences", element: <PreferencesPage /> },
        { path: "/path/create/document", element: <p>документ</p> },
      ],
      { initialEntries: [entry] },
    );
    render(
      <QueryClientProvider client={client}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
  }

  it("бере рік з ?year= і веде назад до документа", async () => {
    renderPage("/path/create/preferences?year=2025");
    expect(screen.getByRole("heading", { name: "Побажання на 2025/2026" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: "Назад до документа" }));
    expect(await screen.findByText("документ")).toBeInTheDocument();
  });

  it("без ?year= бере поточний рік у межах /config", async () => {
    renderPage("/path/create/preferences");
    const year = Math.min(2030, Math.max(2024, new Date().getFullYear()));
    expect(
      await screen.findByRole("heading", { name: `Побажання на ${year}/${year + 1}` }),
    ).toBeInTheDocument();
  });
});
