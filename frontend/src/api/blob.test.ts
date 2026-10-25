// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { configureAuth, requestBlob, setFetch } from "./client";
import { setAccessToken } from "./token";

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const unauthorized = () =>
  json({ code: "UNAUTHORIZED", message: "Немає токена", details: [] }, 401);

const pdf = (disposition?: string) =>
  new Response("%PDF-1.4", {
    status: 200,
    headers: {
      "Content-Type": "application/pdf",
      ...(disposition ? { "Content-Disposition": disposition } : {}),
    },
  });

function authorizationOf(call: unknown[]): string | null {
  const init = call[1] as RequestInit | undefined;
  return new Headers(init?.headers).get("Authorization");
}

beforeEach(() => {
  setAccessToken(null);
  configureAuth({ refresh: async () => null, onAuthLost: () => {} });
});

describe("requestBlob", () => {
  it("повертає вміст і ім'я файлу з Content-Disposition", async () => {
    setFetch(vi.fn().mockResolvedValue(pdf('attachment; filename="plan-2026.pdf"')));
    const result = await requestBlob("/plans/1/export", { query: { format: "pdf" } });
    expect(result.blob.size).toBe(8);
    expect(result.filename).toBe("plan-2026.pdf");
  });

  it("без заголовка ім'я файлу null", async () => {
    setFetch(vi.fn().mockResolvedValue(pdf()));
    expect((await requestBlob("/plans/1/export")).filename).toBeNull();
  });

  it("на 401 оновлює токен і повторює запит, як звичайний request", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(unauthorized()).mockResolvedValueOnce(pdf());
    setFetch(fetchMock);
    setAccessToken("old");
    configureAuth({ refresh: vi.fn().mockResolvedValue("new"), onAuthLost: () => {} });
    await requestBlob("/plans/1/export");
    expect(authorizationOf(fetchMock.mock.calls[1]!)).toBe("Bearer new");
  });

  it("JSON-помилка стає ApiError", async () => {
    setFetch(
      vi
        .fn()
        .mockResolvedValue(
          json({ code: "PLAN_NOT_FOUND", message: "Плану немає", details: [] }, 404),
        ),
    );
    await expect(requestBlob("/plans/9/export")).rejects.toMatchObject({
      status: 404,
      code: "PLAN_NOT_FOUND",
    });
  });

  it("не JSON помилка 502 дає HTTP_502", async () => {
    setFetch(vi.fn().mockResolvedValue(new Response("<html>bad</html>", { status: 502 })));
    await expect(requestBlob("/plans/1/export")).rejects.toMatchObject({ code: "HTTP_502" });
  });

  it("мережева помилка дає NETWORK_ERROR", async () => {
    setFetch(vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(requestBlob("/plans/1/export")).rejects.toMatchObject({
      status: 0,
      code: "NETWORK_ERROR",
    });
  });
});
