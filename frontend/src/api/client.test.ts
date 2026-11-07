// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { ApiError } from "./errors";
import { configureAuth, request, setFetch } from "./client";
import { setAccessToken } from "./token";

function json(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

const unauthorized = () =>
  json({ code: "UNAUTHORIZED", message: "Немає токена", details: [] }, 401);

function authorizationOf(call: unknown[]): string | null {
  const init = call[1] as RequestInit | undefined;
  return new Headers(init?.headers).get("Authorization");
}

beforeEach(() => {
  setAccessToken(null);
  configureAuth({ refresh: async () => null, onAuthLost: () => {} });
});

describe("request", () => {
  it("додає Authorization, коли є токен, і не додає при auth: false", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => json({ ok: true }));
    setFetch(fetchMock);
    setAccessToken("abc");
    await request("/me");
    await request("/config", { auth: false });
    expect(authorizationOf(fetchMock.mock.calls[0]!)).toBe("Bearer abc");
    expect(authorizationOf(fetchMock.mock.calls[1]!)).toBeNull();
  });

  it("розбирає помилку у ApiError з code, details і X-Request-ID", async () => {
    const details = [{ field: "academic_year", message: "Input should be >= 2024" }];
    setFetch(
      vi.fn().mockResolvedValue(
        json({ code: "VALIDATION_ERROR", message: "Невалідні вхідні дані", details }, 422, {
          "X-Request-ID": "rid-1",
        }),
      ),
    );
    const error = await request("/plans", { method: "POST", body: {} }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 422,
      code: "VALIDATION_ERROR",
      details,
      requestId: "rid-1",
    });
  });

  it("не JSON помилка (HTML 502) дає ApiError з кодом HTTP_502", async () => {
    setFetch(vi.fn().mockResolvedValue(new Response("<html>Bad gateway</html>", { status: 502 })));
    const error = await request("/me").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 502, code: "HTTP_502" });
  });

  it("204 повертає undefined", async () => {
    setFetch(vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    await expect(request("/plans/1", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("мережева помилка дає ApiError NETWORK_ERROR зі статусом 0", async () => {
    setFetch(vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const error = await request("/me").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 0, code: "NETWORK_ERROR" });
  });

  it("FormData передається як є, без Content-Type (boundary додає браузер)", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => json({ id: 1 }));
    setFetch(fetchMock);
    const form = new FormData();
    form.append("academic_year", "2026");
    await request("/deanery-documents", { method: "POST", body: form });
    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    expect(init.body).toBe(form);
    expect(new Headers(init.headers).has("Content-Type")).toBe(false);
  });

  it("не губить невідомі поля у відповіді", async () => {
    setFetch(vi.fn().mockResolvedValue(json({ id: 1, nova_ozdoba: "так" })));
    await expect(request<{ id: number }>("/me")).resolves.toEqual({ id: 1, nova_ozdoba: "так" });
  });

  it("додає в адресу лише визначені query-параметри", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => json({}));
    setFetch(fetchMock);
    await request("/plans", { query: { limit: 20, status: undefined, q: "a b" } });
    const url = new URL(String(fetchMock.mock.calls[0]![0]), "http://localhost");
    expect(url.pathname).toBe("/api/v1/plans");
    expect(url.searchParams.get("limit")).toBe("20");
    expect(url.searchParams.get("q")).toBe("a b");
    expect(url.searchParams.has("status")).toBe(false);
  });
});

describe("request: refresh на 401", () => {
  it("один раз оновлює токен і повторює запит", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(unauthorized())
      .mockResolvedValueOnce(json({ ok: true }));
    const refresh = vi.fn().mockResolvedValue("new-token");
    setFetch(fetchMock);
    setAccessToken("old-token");
    configureAuth({ refresh, onAuthLost: () => {} });
    await expect(request("/me")).resolves.toEqual({ ok: true });
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(authorizationOf(fetchMock.mock.calls[1]!)).toBe("Bearer new-token");
  });

  it("другий 401 після refresh кидає UNAUTHORIZED і викликає onAuthLost", async () => {
    setFetch(vi.fn().mockImplementation(async () => unauthorized()));
    const refresh = vi.fn().mockResolvedValue("new-token");
    const onAuthLost = vi.fn();
    setAccessToken("old-token");
    configureAuth({ refresh, onAuthLost });
    const error = await request("/me").catch((e: unknown) => e);
    expect(error).toMatchObject({ status: 401, code: "UNAUTHORIZED" });
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(onAuthLost).toHaveBeenCalledTimes(1);
  });

  it("refresh повернув null: UNAUTHORIZED і onAuthLost без повтору запиту", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => unauthorized());
    const onAuthLost = vi.fn();
    setFetch(fetchMock);
    configureAuth({ refresh: async () => null, onAuthLost });
    await expect(request("/me")).rejects.toMatchObject({ code: "UNAUTHORIZED" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(onAuthLost).toHaveBeenCalledTimes(1);
  });

  it("не оновлює токен для запитів з auth: false", async () => {
    const refresh = vi.fn().mockResolvedValue("x");
    setFetch(vi.fn().mockImplementation(async () => unauthorized()));
    configureAuth({ refresh, onAuthLost: () => {} });
    await expect(request("/auth/microsoft", { method: "POST", auth: false })).rejects.toMatchObject(
      {
        status: 401,
      },
    );
    expect(refresh).not.toHaveBeenCalled();
  });

  it("паралельні 401 викликають refresh один раз", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(async (_url: string, init?: RequestInit) =>
        new Headers(init?.headers).get("Authorization") === "Bearer old"
          ? unauthorized()
          : json({ ok: true }),
      );
    const refresh = vi.fn().mockImplementation(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10));
      return "new";
    });
    setFetch(fetchMock);
    setAccessToken("old");
    configureAuth({ refresh, onAuthLost: () => {} });
    const results = await Promise.all([request("/me"), request("/plans"), request("/disciplines")]);
    expect(results).toEqual([{ ok: true }, { ok: true }, { ok: true }]);
    expect(refresh).toHaveBeenCalledTimes(1);
  });
});

describe("request: тайм-аут", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  /** Підставний fetch, який ніколи не відповідає, але реагує на abort, як справжній. */
  const hangingFetch = () =>
    vi.fn().mockImplementation(
      (_url: string, init?: RequestInit) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        }),
    );

  it("«мовчазний» сервер дає ApiError TIMEOUT після 20 с, а не вічне очікування", async () => {
    vi.useFakeTimers();
    setFetch(hangingFetch());
    const pending = request("/me").catch((e: unknown) => e);
    let settled = false;
    void pending.then(() => (settled = true));
    await vi.advanceTimersByTimeAsync(19_999);
    expect(settled).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    const error = await pending;
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 0, code: "TIMEOUT" });
  });

  it("timeoutMs переозначає ліміт", async () => {
    vi.useFakeTimers();
    setFetch(hangingFetch());
    const pending = request("/me", { timeoutMs: 500 }).catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(500);
    expect(await pending).toMatchObject({ code: "TIMEOUT" });
  });

  it("завантаження файлу (FormData) має довший ліміт, ніж звичайний запит", async () => {
    vi.useFakeTimers();
    setFetch(hangingFetch());
    const form = new FormData();
    form.append("academic_year", "2026");
    const pending = request("/deanery-documents", { method: "POST", body: form }).catch(
      (e: unknown) => e,
    );
    let settled = false;
    void pending.then(() => (settled = true));
    await vi.advanceTimersByTimeAsync(60_000);
    expect(settled).toBe(false);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(await pending).toMatchObject({ code: "TIMEOUT" });
  });

  it("скасування викликачем лишається NETWORK_ERROR, а не TIMEOUT", async () => {
    setFetch(hangingFetch());
    const controller = new AbortController();
    const pending = request("/me", { signal: controller.signal }).catch((e: unknown) => e);
    controller.abort();
    expect(await pending).toMatchObject({ status: 0, code: "NETWORK_ERROR" });
  });

  it("швидка відповідь не лишає активного таймера", async () => {
    vi.useFakeTimers();
    setFetch(vi.fn().mockResolvedValue(json({ ok: true })));
    await expect(request("/me")).resolves.toEqual({ ok: true });
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("request: тимчасовий збій refresh не розлогінює", () => {
  it("мережева помилка refresh: запит падає з NETWORK_ERROR, onAuthLost не викликано", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => unauthorized());
    const onAuthLost = vi.fn();
    setFetch(fetchMock);
    setAccessToken("old-token");
    configureAuth({
      refresh: async () => {
        throw new ApiError(0, "NETWORK_ERROR", "Не вдалося з'єднатися з сервером");
      },
      onAuthLost,
    });
    const error = await request("/me").catch((e: unknown) => e);
    expect(error).toMatchObject({ status: 0, code: "NETWORK_ERROR" });
    expect(onAuthLost).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("5xx під час refresh прокидається користувачу як є, сесія зберігається", async () => {
    const onAuthLost = vi.fn();
    setFetch(vi.fn().mockImplementation(async () => unauthorized()));
    setAccessToken("old-token");
    configureAuth({
      refresh: async () => {
        throw new ApiError(503, "HTTP_503", "Помилка запиту (503)");
      },
      onAuthLost,
    });
    await expect(request("/me")).rejects.toMatchObject({ status: 503 });
    expect(onAuthLost).not.toHaveBeenCalled();
  });

  it("не-ApiError у refresh перетворюється на NETWORK_ERROR", async () => {
    const onAuthLost = vi.fn();
    setFetch(vi.fn().mockImplementation(async () => unauthorized()));
    setAccessToken("old-token");
    configureAuth({
      refresh: async () => {
        throw new Error("щось пішло не так");
      },
      onAuthLost,
    });
    await expect(request("/me")).rejects.toMatchObject({ code: "NETWORK_ERROR" });
    expect(onAuthLost).not.toHaveBeenCalled();
  });

  it("після тимчасового збою наступний запит знову пробує refresh", async () => {
    const refresh = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(0, "NETWORK_ERROR", "x"))
      .mockResolvedValueOnce("new-token");
    setFetch(
      vi
        .fn()
        .mockImplementationOnce(async () => unauthorized())
        .mockImplementationOnce(async () => unauthorized())
        .mockImplementationOnce(async () => json({ ok: true })),
    );
    setAccessToken("old-token");
    configureAuth({ refresh, onAuthLost: () => {} });
    await expect(request("/me")).rejects.toMatchObject({ code: "NETWORK_ERROR" });
    await expect(request("/me")).resolves.toEqual({ ok: true });
    expect(refresh).toHaveBeenCalledTimes(2);
  });
});
