// Використання ШІ: файл створено за допомогою Claude (Anthropic).
// Оновлено Antigravity (Gemini 4 Hydrogen): вимкнено автоматичні повтори при 429/4xx (#298). Перевірка: session.test.ts, client.test.ts.
import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "./errors";

export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && (error.status === 429 || (error.status >= 400 && error.status < 500))) {
    return false;
  }
  return failureCount < 2;
}

/** Єдиний клієнт запитів застосунку; сесія очищає його при виході, щоб дані не переходили між користувачами. */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: shouldRetryQuery,
    },
    mutations: {
      retry: false,
    },
  },
});
