// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { http, HttpResponse } from "msw";
import { getAccessToken } from "../api/token";
import { server } from "../mocks/server";
import { buildAuthorizeUrl, completeLogin, startLogin } from "./login";

const env = { clientId: "client-1", tenant: "organizations", origin: "http://localhost:5173" };

beforeEach(() => {
  sessionStorage.clear();
  vi.stubEnv("VITE_MS_CLIENT_ID", "client-1");
  vi.stubEnv("VITE_MS_TENANT", "organizations");
});
afterEach(() => vi.unstubAllEnvs());

function countExchanges() {
  const counter = { calls: 0 };
  server.use(
    http.post("*/api/v1/auth/microsoft", () => {
      counter.calls += 1;
      return HttpResponse.json({});
    }),
  );
  return counter;
}

describe("buildAuthorizeUrl", () => {
  it("містить усі параметри OAuth2 + PKCE", () => {
    const url = new URL(buildAuthorizeUrl(env, { state: "st", challenge: "ch" }));
    expect(`${url.origin}${url.pathname}`).toBe(
      "https://login.microsoftonline.com/organizations/oauth2/v2.0/authorize",
    );
    expect(url.searchParams.get("client_id")).toBe("client-1");
    expect(url.searchParams.get("response_type")).toBe("code");
    expect(url.searchParams.get("redirect_uri")).toBe("http://localhost:5173/auth/callback");
    expect(url.searchParams.get("scope")).toBe("openid email profile");
    expect(url.searchParams.get("code_challenge")).toBe("ch");
    expect(url.searchParams.get("code_challenge_method")).toBe("S256");
    expect(url.searchParams.get("state")).toBe("st");
    expect(url.searchParams.get("response_mode")).toBe("query");
  });
});

describe("startLogin", () => {
  it("зберігає verifier і state та веде на Microsoft", async () => {
    const navigate = vi.fn();
    await startLogin(navigate);
    const verifier = sessionStorage.getItem("pkce_verifier");
    const state = sessionStorage.getItem("oauth_state");
    expect(verifier).toHaveLength(43);
    expect(state).toBeTruthy();
    const url = new URL(navigate.mock.calls[0]![0] as string);
    expect(url.searchParams.get("state")).toBe(state);
    expect(url.searchParams.get("code_challenge")).toBeTruthy();
    expect(url.searchParams.get("code_challenge")).not.toBe(verifier);
  });

  it("без VITE_MS_CLIENT_ID кидає OAUTH_NOT_CONFIGURED і нікуди не веде", async () => {
    vi.stubEnv("VITE_MS_CLIENT_ID", "");
    const navigate = vi.fn();
    await expect(startLogin(navigate)).rejects.toMatchObject({ code: "OAUTH_NOT_CONFIGURED" });
    expect(navigate).not.toHaveBeenCalled();
  });
});

describe("completeLogin", () => {
  beforeEach(() => {
    sessionStorage.setItem("pkce_verifier", "v".repeat(43));
    sessionStorage.setItem("oauth_state", "state-1");
  });

  it("чужий state: OAUTH_STATE_MISMATCH без запиту до API", async () => {
    const counter = countExchanges();
    await expect(completeLogin("?code=c&state=WRONG")).rejects.toMatchObject({
      code: "OAUTH_STATE_MISMATCH",
    });
    expect(counter.calls).toBe(0);
  });

  it("error у відповіді Microsoft: OAUTH_ERROR без запиту до API", async () => {
    const counter = countExchanges();
    await expect(completeLogin("?error=access_denied&state=state-1")).rejects.toMatchObject({
      code: "OAUTH_ERROR",
    });
    expect(counter.calls).toBe(0);
  });

  it("немає code: OAUTH_MISSING_CODE без запиту до API", async () => {
    const counter = countExchanges();
    await expect(completeLogin("?state=state-1")).rejects.toMatchObject({
      code: "OAUTH_MISSING_CODE",
    });
    expect(counter.calls).toBe(0);
  });

  it("успіх: повертає AuthResponse, ставить токен і чистить сховище", async () => {
    const auth = await completeLogin("?code=c&state=state-1");
    expect(auth.user.id).toBe(42);
    expect(getAccessToken()).toBe("mock-access-token");
    expect(sessionStorage.getItem("pkce_verifier")).toBeNull();
    expect(sessionStorage.getItem("oauth_state")).toBeNull();
  });

  it("помилка сервера (домен) пробрасується й теж чистить сховище", async () => {
    server.use(
      http.post("*/api/v1/auth/microsoft", () =>
        HttpResponse.json(
          { code: "DOMAIN_NOT_ALLOWED", message: "Не той домен", details: [] },
          { status: 403 },
        ),
      ),
    );
    await expect(completeLogin("?code=c&state=state-1")).rejects.toMatchObject({
      code: "DOMAIN_NOT_ALLOWED",
      status: 403,
    });
    expect(sessionStorage.getItem("pkce_verifier")).toBeNull();
  });
});
