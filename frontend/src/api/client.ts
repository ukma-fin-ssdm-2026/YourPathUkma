// Використання ШІ: Codex виправив #220; перевірка: регресії Vitest, ESLint і TypeScript.
// Використання ШІ: Antigravity (Gemini 4 Hydrogen) додав парсинг Retry-After (#298). Перевірка: Vitest.
// Використання ШІ: Codex відкрив заголовки бінарної відповіді для кадрів САЗ. Перевірка: Vitest.
// Використання ШІ: підтримку JSON-файлів додано Codex. Перевірка: Vitest.
// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: client.test.ts.
import { parseDispositionFilename } from "../lib/download";
import { ApiError, type ErrorDetail } from "./errors";
import { getAccessToken, setAccessToken } from "./token";

const BASE_URL: string = import.meta.env.VITE_API_BASE ?? "/api/v1";

/** Скільки чекаємо відповідь сервера (разом із читанням тіла); завантаження файлів і PDF довші. */
const DEFAULT_TIMEOUT_MS = 20_000;
const UPLOAD_TIMEOUT_MS = 120_000;
const BLOB_TIMEOUT_MS = 60_000;

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined>;
  /** За замовчуванням true: додає Bearer-токен і один раз пробує refresh на 401. */
  auth?: boolean;
  signal?: AbortSignal;
  /** Заголовок Accept; за замовчуванням JSON. */
  accept?: string;
  /** Максимальний час очікування відповіді, мс. За замовчуванням 20 с (120 с для FormData). */
  timeoutMs?: number;
}

interface AuthHandlers {
  /** Новий токен; `null`, якщо сесія недійсна. Виняток означає тимчасовий збій (мережа, тайм-аут, 5xx). */
  refresh: () => Promise<string | null>;
  onAuthLost: () => void;
}

const responseCleanups = new WeakMap<Response, { cleanup: () => void; timedOut: () => boolean }>();
function releaseResponse(response: Response): void {
  responseCleanups.get(response)?.cleanup();
  responseCleanups.delete(response);
}

let doFetch: typeof fetch = (...args) => fetch(...args);
let authHandlers: AuthHandlers = { refresh: async () => null, onAuthLost: () => {} };
let refreshInFlight: Promise<string | null> | null = null;

export function setFetch(replacement: typeof fetch): void {
  doFetch = replacement;
}

export function configureAuth(handlers: AuthHandlers): void {
  authHandlers = handlers;
  refreshInFlight = null;
}

/** Усі паралельні 401 ділять один виклик refresh. Тимчасовий збій refresh прокидається як виняток. */
function refreshOnce(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = Promise.resolve()
      .then(() => authHandlers.refresh())
      .then((token) => {
        setAccessToken(token);
        return token;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

function buildUrl(path: string, query: RequestOptions["query"]): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined) params.set(key, String(value));
  }
  const search = params.toString();
  return `${BASE_URL}${path}${search ? `?${search}` : ""}`;
}

async function send(
  path: string,
  options: RequestOptions,
  useAuth: boolean,
): Promise<{ response: Response; tokenUsed: string | null }> {
  const tokenUsed = useAuth ? getAccessToken() : null;
  const headers = new Headers({ Accept: options.accept ?? "application/json" });
  const isForm = options.body instanceof FormData;
  const isFile = options.body instanceof Blob;
  if (options.body !== undefined && !isForm) headers.set("Content-Type", "application/json");
  if (tokenUsed) headers.set("Authorization", `Bearer ${tokenUsed}`);

  // Без тайм-ауту запит до «мовчазного» сервера висить вічно (і «Завантаження…» разом із ним)
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(
    () => {
      timedOut = true;
      controller.abort();
    },
    options.timeoutMs ?? (isForm || isFile ? UPLOAD_TIMEOUT_MS : DEFAULT_TIMEOUT_MS),
  );
  const abortWithCaller = () => controller.abort();
  if (options.signal?.aborted) controller.abort();
  else options.signal?.addEventListener("abort", abortWithCaller, { once: true });

  const cleanup = () => {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", abortWithCaller);
  };
  let handedOff = false;
  try {
    const response = await doFetch(buildUrl(path, options.query), {
      method: options.method ?? "GET",
      headers,
      body:
        options.body === undefined
          ? undefined
          : isForm || isFile
            ? (options.body as FormData | Blob)
            : JSON.stringify(options.body),
      credentials: "include",
      signal: controller.signal,
    });
    responseCleanups.set(response, { cleanup, timedOut: () => timedOut });
    handedOff = true;
    return { response, tokenUsed };
  } catch (error) {
    if (options.signal?.aborted) throw error;
    if (timedOut) throw new ApiError(0, "TIMEOUT", "Сервер не відповів вчасно. Спробуйте ще раз");
    throw new ApiError(0, "NETWORK_ERROR", "Не вдалося з'єднатися з сервером");
  } finally {
    if (!handedOff) cleanup();
  }
}

function parseRetryAfter(header: string | null): number | null {
  if (!header) return null;
  const parsed = Number.parseInt(header.trim(), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    return await parseApiError(response);
  } finally {
    releaseResponse(response);
  }
}

async function parseApiError(response: Response): Promise<ApiError> {
  const requestId = response.headers.get("X-Request-ID");
  const retryAfter = parseRetryAfter(response.headers.get("Retry-After"));
  if (response.status >= 500) {
    return new ApiError(
      response.status,
      `HTTP_${response.status}`,
      "Сервіс тимчасово недоступний. Спробуйте ще раз",
      [],
      requestId,
      retryAfter,
    );
  }
  try {
    const data = (await response.json()) as {
      code?: unknown;
      message?: unknown;
      details?: unknown;
    };
    if (typeof data.code === "string") {
      const message = typeof data.message === "string" ? data.message : "Помилка запиту";
      const details = Array.isArray(data.details) ? (data.details as ErrorDetail[]) : [];
      return new ApiError(response.status, data.code, message, details, requestId, retryAfter);
    }
  } catch {
    // тіло не JSON (наприклад, HTML від проксі): падаємо на загальну помилку нижче
  }
  return new ApiError(
    response.status,
    `HTTP_${response.status}`,
    `Помилка запиту (${response.status})`,
    [],
    requestId,
    retryAfter,
  );
}

/** Виконує запит з автентифікацією та одноразовим refresh; повертає лише успішну відповідь. */
async function execute(path: string, options: RequestOptions): Promise<Response> {
  const useAuth = options.auth !== false;
  let { response, tokenUsed } = await send(path, options, useAuth);

  if (response.status === 401 && useAuth) {
    releaseResponse(response);
    // Якщо токен уже оновив інший запит, достатньо повторити; інакше оновлюємо самі.
    if (tokenUsed === getAccessToken()) {
      let fresh: string | null;
      try {
        fresh = await refreshOnce();
      } catch (error) {
        // Тимчасовий збій refresh (мережа, тайм-аут, 5xx) не означає, що сесія недійсна: не розлогінюємо
        throw error instanceof ApiError
          ? error
          : new ApiError(0, "NETWORK_ERROR", "Не вдалося з'єднатися з сервером");
      }
      if (!fresh) {
        authHandlers.onAuthLost();
        throw await toApiError(response);
      }
    }
    ({ response, tokenUsed } = await send(path, options, useAuth));
    if (response.status === 401) {
      authHandlers.onAuthLost();
      throw await toApiError(response);
    }
  }

  if (!response.ok) throw await toApiError(response);
  return response;
}

export async function request<T = void>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await execute(path, options);
  if (response.status === 204) {
    releaseResponse(response);
    return undefined as T;
  }
  try {
    return (await response.json()) as T;
  } catch (error) {
    if (responseCleanups.get(response)?.timedOut()) {
      throw new ApiError(0, "TIMEOUT", "Сервер не відповів вчасно. Спробуйте ще раз");
    }
    if (options.signal?.aborted) throw error;
    throw new ApiError(
      response.status,
      "BAD_RESPONSE",
      "Сервер повернув некоректну відповідь",
      [],
      response.headers.get("X-Request-ID"),
    );
  } finally {
    releaseResponse(response);
  }
}

/** Бінарна відповідь (наприклад, PDF) з іменем файлу з Content-Disposition. */
export async function requestBlob(
  path: string,
  options: RequestOptions = {},
): Promise<{ blob: Blob; filename: string | null; headers: Headers }> {
  const response = await execute(path, {
    accept: "application/pdf, application/json;q=0.5",
    timeoutMs: BLOB_TIMEOUT_MS,
    ...options,
  });
  try {
    return {
      blob: await response.blob(),
      headers: response.headers,
      filename: parseDispositionFilename(response.headers.get("Content-Disposition")),
    };
  } catch (error) {
    if (responseCleanups.get(response)?.timedOut()) {
      throw new ApiError(0, "TIMEOUT", "Сервер не відповів вчасно. Спробуйте ще раз");
    }
    throw error;
  } finally {
    releaseResponse(response);
  }
}
