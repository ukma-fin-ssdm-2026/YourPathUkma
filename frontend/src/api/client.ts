// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: client.test.ts.
import { parseDispositionFilename } from "../lib/download";
import { ApiError, type ErrorDetail } from "./errors";
import { getAccessToken, setAccessToken } from "./token";

const BASE_URL: string = import.meta.env.VITE_API_BASE ?? "/api/v1";

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined>;
  /** За замовчуванням true: додає Bearer-токен і один раз пробує refresh на 401. */
  auth?: boolean;
  signal?: AbortSignal;
  /** Заголовок Accept; за замовчуванням JSON. */
  accept?: string;
}

interface AuthHandlers {
  refresh: () => Promise<string | null>;
  onAuthLost: () => void;
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

/** Усі паралельні 401 ділять один виклик refresh. */
function refreshOnce(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = Promise.resolve()
      .then(() => authHandlers.refresh())
      .catch(() => null)
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
  if (options.body !== undefined && !isForm) headers.set("Content-Type", "application/json");
  if (tokenUsed) headers.set("Authorization", `Bearer ${tokenUsed}`);
  try {
    const response = await doFetch(buildUrl(path, options.query), {
      method: options.method ?? "GET",
      headers,
      body:
        options.body === undefined
          ? undefined
          : isForm
            ? (options.body as FormData)
            : JSON.stringify(options.body),
      credentials: "include",
      signal: options.signal,
    });
    return { response, tokenUsed };
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Не вдалося з'єднатися з сервером");
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  const requestId = response.headers.get("X-Request-ID");
  try {
    const data = (await response.json()) as {
      code?: unknown;
      message?: unknown;
      details?: unknown;
    };
    if (typeof data.code === "string") {
      const message = typeof data.message === "string" ? data.message : "Помилка запиту";
      const details = Array.isArray(data.details) ? (data.details as ErrorDetail[]) : [];
      return new ApiError(response.status, data.code, message, details, requestId);
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
  );
}

/** Виконує запит з автентифікацією та одноразовим refresh; повертає лише успішну відповідь. */
async function execute(path: string, options: RequestOptions): Promise<Response> {
  const useAuth = options.auth !== false;
  let { response, tokenUsed } = await send(path, options, useAuth);

  if (response.status === 401 && useAuth) {
    // Якщо токен уже оновив інший запит, достатньо повторити; інакше оновлюємо самі.
    if (tokenUsed === getAccessToken()) {
      const fresh = await refreshOnce();
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
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Бінарна відповідь (наприклад, PDF) з іменем файлу з Content-Disposition. */
export async function requestBlob(
  path: string,
  options: RequestOptions = {},
): Promise<{ blob: Blob; filename: string | null }> {
  const response = await execute(path, { accept: "application/pdf, application/json;q=0.5", ...options });
  return {
    blob: await response.blob(),
    filename: parseDispositionFilename(response.headers.get("Content-Disposition")),
  };
}
