// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { useSession } from "../../auth/session";
import { db } from "../../mocks/db";
import { authResponse } from "../../mocks/fixtures";
import { server } from "../../mocks/server";
import { configHandler, directionsHandler } from "../../test/handlers";
import { defaultPreferences } from "./preferences";
import { PreferencesForm } from "./PreferencesForm";

const NAMES = ["Data Science", "Cybersecurity", "Web Development", "UX Research"];

function renderForm() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <PreferencesForm year={2026} />
    </QueryClientProvider>,
  );
}

function asStudent(course: 1 | 2 | 3 | 4) {
  const student = db.me.student!;
  db.me = {
    ...db.me,
    student: {
      ...student,
      course_year: course,
      onboarding_required: false,
      load_levels_mode: course === 4 ? "auto" : "manual",
    },
  };
}

const chip = (name: string) => screen.findByRole("button", { name });
const loadGroup = (season: string) => screen.getByRole("group", { name: `Навантаження: ${season}` });

beforeEach(() => {
  useSession.getState().setAuthenticated(authResponse());
  server.use(configHandler(), directionsHandler(NAMES));
  asStudent(3);
});

describe("напрямки", () => {
  it("показує напрямки й позначає збережені", async () => {
    db.preferences[2026] = { ...defaultPreferences(2026), direction_ids: [1, 2] };
    renderForm();
    expect(await chip("Data Science")).toHaveAttribute("aria-pressed", "true");
    expect(await chip("Cybersecurity")).toHaveAttribute("aria-pressed", "true");
    expect(await chip("Web Development")).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByText("2 / 3")).toBeInTheDocument();
  });

  it("після трьох вибраних четвертий недоступний", async () => {
    renderForm();
    await userEvent.click(await chip("Data Science"));
    await userEvent.click(await chip("Cybersecurity"));
    await userEvent.click(await chip("Web Development"));
    expect(screen.getByText("3 / 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "UX Research" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Web Development" }));
    expect(screen.getByRole("button", { name: "UX Research" })).toBeEnabled();
  });
});

describe("навантаження", () => {
  it("пояснює пороги з /config", async () => {
    renderForm();
    expect(
      await screen.findByText("Низьке — до 20 годин на тиждень, середнє — 20–23, високе — 23–25."),
    ).toBeInTheDocument();
  });

  it("низьке навантаження влітку й восени показує відповідні попередження", async () => {
    renderForm();
    await screen.findByRole("group", { name: "Навантаження: літо" });
    await userEvent.click(within(loadGroup("літо")).getByRole("button", { name: "Низьке" }));
    expect(
      screen.getByText(
        "Влітку обрано низьке навантаження: щоб набрати 57–60 кредитів за рік, навантаження наступних років зросте.",
      ),
    ).toBeInTheDocument();
    await userEvent.click(within(loadGroup("осінь")).getByRole("button", { name: "Низьке" }));
    expect(screen.getByText(/^Восени обрано низьке навантаження/)).toBeInTheDocument();
  });

  it("збережене низьке навантаження видно одразу", async () => {
    db.preferences[2026] = {
      ...defaultPreferences(2026),
      load_levels: { autumn: "medium", spring: "medium", summer: "low" },
    };
    renderForm();
    expect(await screen.findByText(/^Влітку обрано низьке навантаження/)).toBeInTheDocument();
  });

  it("для 4 курсу вибір заблоковано з поясненням", async () => {
    asStudent(4);
    renderForm();
    expect(
      await screen.findByText("Для 4 курсу навантаження розраховується автоматично."),
    ).toBeInTheDocument();
    for (const button of within(loadGroup("осінь")).getAllByRole("button")) {
      expect(button).toBeDisabled();
    }
  });
});

describe("збереження", () => {
  it("надсилає вибрані напрямки й навантаження та підтверджує збереження", async () => {
    renderForm();
    await userEvent.click(await chip("Data Science"));
    await userEvent.click(within(loadGroup("весна")).getByRole("button", { name: "Високе" }));
    await userEvent.click(screen.getByRole("button", { name: "Зберегти побажання" }));
    expect(await screen.findByText("Побажання збережено")).toBeInTheDocument();
    expect(db.preferences[2026]).toMatchObject({
      direction_ids: [1],
      load_levels: { autumn: "medium", spring: "high", summer: "medium" },
    });
  });

  it("помилка 422 показується біля напрямків", async () => {
    server.use(
      http.put("*/api/v1/preferences/2026", () =>
        HttpResponse.json(
          {
            code: "VALIDATION_ERROR",
            message: "Невалідні вхідні дані",
            details: [{ field: "direction_ids", message: "Не більше 3 напрямків" }],
          },
          { status: 422 },
        ),
      ),
    );
    renderForm();
    await userEvent.click(await chip("Data Science"));
    await userEvent.click(screen.getByRole("button", { name: "Зберегти побажання" }));
    expect(await screen.findByText("Не більше 3 напрямків")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Побажання збережено")).not.toBeInTheDocument());
  });

  it("зміна форми після збереження прибирає позначку «збережено»", async () => {
    renderForm();
    await userEvent.click(await chip("Data Science"));
    await userEvent.click(screen.getByRole("button", { name: "Зберегти побажання" }));
    await screen.findByText("Побажання збережено");
    await userEvent.click(screen.getByRole("button", { name: "Cybersecurity" }));
    expect(screen.queryByText("Побажання збережено")).not.toBeInTheDocument();
  });
});
