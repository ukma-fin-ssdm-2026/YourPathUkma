// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: handlers.test.ts.
// Спільні помічники MSW-обробників.
import { HttpResponse } from "msw";
import type { ErrorDetail } from "../api/errors";

export const API = "*/api/v1";

export function apiError(
  status: number,
  code: string,
  message: string,
  details: ErrorDetail[] = [],
  headers?: Record<string, string>,
) {
  return HttpResponse.json({ code, message, details }, { status, headers });
}

export const unauthorized = () =>
  apiError(401, "UNAUTHORIZED", "Відсутній або некоректний токен авторизації");

export const hasAuth = (request: Request) => Boolean(request.headers.get("Authorization"));

/** Зріз масиву за `limit`/`offset` з адреси та відповідний `pagination`. */
export function paginate<T>(items: T[], url: URL, defaultLimit = 20) {
  const limit = Number(url.searchParams.get("limit") ?? defaultLimit);
  const offset = Number(url.searchParams.get("offset") ?? 0);
  return {
    page: items.slice(offset, offset + limit),
    pagination: { limit, offset, total: items.length, has_more: offset + limit < items.length },
  };
}
