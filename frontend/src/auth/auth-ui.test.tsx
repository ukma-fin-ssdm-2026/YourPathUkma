// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { StrictMode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { RouterProvider, createMemoryRouter, type RouteObject } from "react-router";
import { ConnectedLayout } from "../app/ConnectedLayout";
import { authResponse, mockUser } from "../mocks/fixtures";
import { server } from "../mocks/server";
import { CallbackPage } from "./CallbackPage";
import { LoginPage } from "./LoginPage";
import { RequireAdmin, RequireAuth } from "./RequireAuth";
import { useSession } from "./session";

function renderRoutes(
  routes: RouteObject[],
  entry: string | { pathname: string; state: unknown },
  strict = false,
) {
  const router = createMemoryRouter(routes, { initialEntries: [entry] });
  const ui = <RouterProvider router={router} />;
  render(strict ? <StrictMode>{ui}</StrictMode> : ui);
  return router;
}

const guarded: RouteObject[] = [
  { element: <RequireAuth />, children: [{ path: "/", element: <p>секрет</p> }] },
  { path: "/login", element: <p>сторінка входу</p> },
];

beforeEach(() => {
  useSession.setState({ status: "loading", user: null });
  sessionStorage.clear();
});

describe("RequireAuth / RequireAdmin", () => {
  it("поки сесія відновлюється, показує «Завантаження…» і не редіректить", () => {
    renderRoutes(guarded, "/");
    expect(screen.getByRole("status")).toHaveTextContent("Завантаження…");
    expect(screen.queryByText("сторінка входу")).not.toBeInTheDocument();
  });

  it("анонім потрапляє на /login", async () => {
    useSession.setState({ status: "anonymous", user: null });
    renderRoutes(guarded, "/");
    expect(await screen.findByText("сторінка входу")).toBeInTheDocument();
  });

  it("автентифікований бачить вкладений маршрут", () => {
    useSession.getState().setAuthenticated(authResponse());
    renderRoutes(guarded, "/");
    expect(screen.getByText("секрет")).toBeInTheDocument();
  });

  it("RequireAdmin пускає лише адміністратора", async () => {
    const routes: RouteObject[] = [
      { element: <RequireAdmin />, children: [{ path: "/admin", element: <p>адмінка</p> }] },
      { path: "/", element: <p>головна</p> },
    ];
    useSession.setState({ status: "authenticated", user: mockUser });
    const { unmount } = render(
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/admin"] })} />,
    );
    expect(await screen.findByText("головна")).toBeInTheDocument();
    unmount();

    useSession.setState({ status: "authenticated", user: { ...mockUser, role: "admin" } });
    render(<RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/admin"] })} />);
    expect(await screen.findByText("адмінка")).toBeInTheDocument();
  });
});

describe("LoginPage", () => {
  const loginRoutes = (onLogin?: () => Promise<void>): RouteObject[] => [
    { path: "/login", element: <LoginPage onLogin={onLogin} /> },
    { path: "/", element: <p>головна</p> },
  ];

  it("кнопка «Увійти через Microsoft» запускає вхід", async () => {
    useSession.setState({ status: "anonymous", user: null });
    const onLogin = vi.fn().mockResolvedValue(undefined);
    renderRoutes(loginRoutes(onLogin), "/login");
    await userEvent.click(screen.getByRole("button", { name: /Увійти через Microsoft/ }));
    expect(onLogin).toHaveBeenCalledTimes(1);
  });

  it("показує повідомлення про домен і код помилки", () => {
    useSession.setState({ status: "anonymous", user: null });
    renderRoutes(loginRoutes(), {
      pathname: "/login",
      state: { error: { code: "DOMAIN_NOT_ALLOWED", message: "x", requestId: "a41f-9c2e" } },
    });
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Цей обліковий запис не належить до НаУКМА. Увійдіть з пошти @ukma.edu.ua.",
    );
    expect(screen.getByText(/Код помилки: a41f-9c2e/)).toBeInTheDocument();
  });

  it("показує помилку запуску входу, якщо онлайн-вхід не налаштовано", async () => {
    useSession.setState({ status: "anonymous", user: null });
    const failing = vi.fn().mockRejectedValue(
      Object.assign(new Error("Вхід не налаштовано: немає VITE_MS_CLIENT_ID"), {
        code: "OAUTH_NOT_CONFIGURED",
      }),
    );
    renderRoutes(loginRoutes(failing), "/login");
    await userEvent.click(screen.getByRole("button", { name: /Увійти через Microsoft/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Вхід не налаштовано");
  });

  it("автентифікованого відправляє на головну", async () => {
    useSession.getState().setAuthenticated(authResponse());
    renderRoutes(loginRoutes(), "/login");
    expect(await screen.findByText("головна")).toBeInTheDocument();
  });
});

describe("CallbackPage", () => {
  const callbackRoutes: RouteObject[] = [
    { path: "/auth/callback", element: <CallbackPage /> },
    { path: "/login", element: <LoginPage onLogin={async () => {}} /> },
    { path: "/", element: <p>головна</p> },
  ];

  beforeEach(() => {
    sessionStorage.setItem("pkce_verifier", "v".repeat(43));
    sessionStorage.setItem("oauth_state", "s1");
  });

  it("успіх: сесія автентифікована, перехід на головну", async () => {
    renderRoutes(callbackRoutes, "/auth/callback?code=c&state=s1");
    expect(await screen.findByText("головна")).toBeInTheDocument();
    expect(useSession.getState().status).toBe("authenticated");
  });

  it("error від Microsoft: повернення на /login з повідомленням", async () => {
    const router = renderRoutes(callbackRoutes, "/auth/callback?error=access_denied&state=s1");
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(router.state.location.state).toMatchObject({ error: { code: "OAUTH_ERROR" } });
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("домен не дозволено: /login з DOMAIN_NOT_ALLOWED і кодом помилки", async () => {
    const router = renderRoutes(callbackRoutes, "/auth/callback?code=blocked&state=s1");
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(router.state.location.state).toMatchObject({ error: { code: "DOMAIN_NOT_ALLOWED" } });
    expect(await screen.findByText(/Код помилки: a41f-9c2e/)).toBeInTheDocument();
  });

  it("у StrictMode код обмінюється один раз", async () => {
    let calls = 0;
    server.use(
      http.post("*/api/v1/auth/microsoft", () => {
        calls += 1;
        return HttpResponse.json(authResponse());
      }),
    );
    renderRoutes(callbackRoutes, "/auth/callback?code=c&state=s1", true);
    expect(await screen.findByText("головна")).toBeInTheDocument();
    expect(calls).toBe(1);
  });
});

describe("ConnectedLayout", () => {
  it("«Вийти» завершує сесію й веде на /login", async () => {
    useSession.getState().setAuthenticated(authResponse());
    renderRoutes(
      [
        { element: <ConnectedLayout />, children: [{ path: "/", element: <p>головна</p> }] },
        { path: "/login", element: <p>сторінка входу</p> },
      ],
      "/",
    );
    expect(screen.getByText("Владислав Смирнов")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Вийти" }));
    expect(await screen.findByText("сторінка входу")).toBeInTheDocument();
    expect(useSession.getState().status).toBe("anonymous");
  });
});
