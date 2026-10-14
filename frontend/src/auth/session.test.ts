// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { http, HttpResponse } from "msw";
import { request } from "../api/client";
import { queryClient } from "../api/queryClient";
import { getAccessToken, setAccessToken } from "../api/token";
import type { AuthResponse } from "../api/types";
import { server } from "../mocks/server";
import { installAuth, restoreSession, signOut, useSession } from "./session";

beforeEach(() => {
  useSession.setState({ status: "loading", user: null });
});

async function signInOnServer() {
  await request<AuthResponse>("/auth/microsoft", { method: "POST", auth: false, body: {} });
}

describe("session", () => {
  it("початковий стан loading", () => {
    expect(useSession.getState().status).toBe("loading");
  });

  it("restoreSession без входу дає anonymous", async () => {
    await restoreSession();
    expect(useSession.getState()).toMatchObject({ status: "anonymous", user: null });
    expect(getAccessToken()).toBeNull();
  });

  it("restoreSession після входу дає authenticated з користувачем і токеном", async () => {
    await signInOnServer();
    await restoreSession();
    expect(useSession.getState().status).toBe("authenticated");
    expect(useSession.getState().user?.id).toBe(42);
    expect(getAccessToken()).toBe("mock-access-token");
  });

  it("signOut скидає сесію й токен", async () => {
    await signInOnServer();
    await restoreSession();
    await signOut();
    expect(useSession.getState().status).toBe("anonymous");
    expect(getAccessToken()).toBeNull();
  });

  it("signOut очищає кеш запитів, щоб наступний користувач не бачив чужі дані", async () => {
    queryClient.setQueryData(["me"], { id: 42, full_name: "Попередній користувач" });
    await signInOnServer();
    await restoreSession();
    await signOut();
    expect(queryClient.getQueryData(["me"])).toBeUndefined();
  });

  it("втрата сесії (onAuthLost) теж очищає кеш запитів", async () => {
    queryClient.setQueryData(["plans", "all"], { plans: [] });
    installAuth();
    setAccessToken("expired");
    server.use(
      http.get("*/api/v1/me", () =>
        HttpResponse.json({ code: "UNAUTHORIZED", message: "x", details: [] }, { status: 401 }),
      ),
    );
    await expect(request("/me")).rejects.toMatchObject({ code: "UNAUTHORIZED" });
    expect(queryClient.getQueryData(["plans", "all"])).toBeUndefined();
  });

  it("installAuth: прострочений токен тихо оновлюється через refresh", async () => {
    server.use(
      http.get("*/api/v1/me", ({ request: req }) =>
        req.headers.get("Authorization") === "Bearer mock-access-token"
          ? HttpResponse.json({ id: 42 })
          : HttpResponse.json({ code: "UNAUTHORIZED", message: "x", details: [] }, { status: 401 }),
      ),
    );
    await signInOnServer();
    installAuth();
    setAccessToken("expired");
    await expect(request("/me")).resolves.toEqual({ id: 42 });
    expect(useSession.getState().status).toBe("authenticated");
  });

  it("installAuth: якщо refresh не вдався, сесія стає anonymous", async () => {
    installAuth();
    setAccessToken("expired");
    server.use(
      http.get("*/api/v1/me", () =>
        HttpResponse.json({ code: "UNAUTHORIZED", message: "x", details: [] }, { status: 401 }),
      ),
    );
    await expect(request("/me")).rejects.toMatchObject({ code: "UNAUTHORIZED" });
    expect(useSession.getState().status).toBe("anonymous");
  });
});
