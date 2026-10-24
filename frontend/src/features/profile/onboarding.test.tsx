// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { RouterProvider, createMemoryRouter, type RouteObject } from "react-router";
import { useSession } from "../../auth/session";
import { authResponse, emptyMe } from "../../mocks/fixtures";
import { server } from "../../mocks/server";
import { OnboardingPage } from "./OnboardingPage";
import { RequireOnboarded } from "./RequireOnboarded";

function renderAt(path: string, routes: RouteObject[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

function onboardedMe() {
  const me = emptyMe();
  return {
    ...me,
    student: { ...me.student!, onboarding_required: false, course_year: 3 as const },
  };
}

beforeEach(() => {
  useSession.getState().setAuthenticated(authResponse());
});

describe("RequireOnboarded", () => {
  const routes: RouteObject[] = [
    { element: <RequireOnboarded />, children: [{ path: "/", element: <p>головна</p> }] },
    { path: "/onboarding", element: <p>онбординг</p> },
  ];

  it("студента без онбордингу відправляє на /onboarding", async () => {
    renderAt("/", routes);
    expect(await screen.findByText("онбординг")).toBeInTheDocument();
  });

  it("студента з пройденим онбордингом пускає далі", async () => {
    server.use(http.get("*/api/v1/me", () => HttpResponse.json(onboardedMe())));
    renderAt("/", routes);
    expect(await screen.findByText("головна")).toBeInTheDocument();
  });

  it("адміністратора без профілю студента пускає далі", async () => {
    server.use(
      http.get("*/api/v1/me", () =>
        HttpResponse.json({ ...emptyMe(), role: "admin", student: null }),
      ),
    );
    renderAt("/", routes);
    expect(await screen.findByText("головна")).toBeInTheDocument();
  });
});

describe("OnboardingPage", () => {
  const routes: RouteObject[] = [
    { path: "/onboarding", element: <OnboardingPage /> },
    { path: "/", element: <p>головна</p> },
  ];

  it("показує вибір курсу 1-4 і поле «Спеціальність»", async () => {
    renderAt("/onboarding", routes);
    for (const course of ["1", "2", "3", "4"]) {
      expect(await screen.findByRole("button", { name: course })).toHaveAttribute(
        "aria-pressed",
        "false",
      );
    }
    expect(screen.getByLabelText("Спеціальність")).toBeInTheDocument();
  });

  it("без курсу показує підказку й не надсилає запит", async () => {
    let calls = 0;
    server.use(
      http.post("*/api/v1/me/onboarding", () => {
        calls += 1;
        return HttpResponse.json(onboardedMe());
      }),
    );
    renderAt("/onboarding", routes);
    await userEvent.type(
      await screen.findByLabelText("Спеціальність"),
      "Інженерія програмного забезпечення",
    );
    await userEvent.click(screen.getByRole("button", { name: "Продовжити" }));
    expect(await screen.findByText("Оберіть курс")).toBeInTheDocument();
    expect(calls).toBe(0);
  });

  it("для 1 курсу показує, що план формує деканат", async () => {
    renderAt("/onboarding", routes);
    await userEvent.click(await screen.findByRole("button", { name: "1" }));
    expect(
      screen.getByText("Для 1 курсу план формує деканат, тож у застосунку його не створити."),
    ).toBeInTheDocument();
  });

  it("успішне надсилання веде на головну", async () => {
    renderAt("/onboarding", routes);
    await userEvent.click(await screen.findByRole("button", { name: "3" }));
    await userEvent.type(
      screen.getByLabelText("Спеціальність"),
      "Інженерія програмного забезпечення",
    );
    await userEvent.click(screen.getByRole("button", { name: "Продовжити" }));
    expect(await screen.findByText("головна")).toBeInTheDocument();
  });

  it("помилка 422 показується біля поля", async () => {
    renderAt("/onboarding", routes);
    await userEvent.click(await screen.findByRole("button", { name: "3" }));
    await userEvent.type(screen.getByLabelText("Спеціальність"), "І");
    await userEvent.click(screen.getByRole("button", { name: "Продовжити" }));
    expect(
      await screen.findByText("String should have from 2 to 150 characters"),
    ).toBeInTheDocument();
  });

  it("409 ALREADY_ONBOARDED веде на головну", async () => {
    server.use(
      http.post("*/api/v1/me/onboarding", () =>
        HttpResponse.json(
          { code: "ALREADY_ONBOARDED", message: "Уже", details: [] },
          { status: 409 },
        ),
      ),
    );
    renderAt("/onboarding", routes);
    await userEvent.click(await screen.findByRole("button", { name: "3" }));
    await userEvent.type(
      screen.getByLabelText("Спеціальність"),
      "Інженерія програмного забезпечення",
    );
    await userEvent.click(screen.getByRole("button", { name: "Продовжити" }));
    expect(await screen.findByText("головна")).toBeInTheDocument();
  });

  it("студента, що вже пройшов онбординг, відправляє на головну", async () => {
    server.use(http.get("*/api/v1/me", () => HttpResponse.json(onboardedMe())));
    renderAt("/onboarding", routes);
    expect(await screen.findByText("головна")).toBeInTheDocument();
  });
});
