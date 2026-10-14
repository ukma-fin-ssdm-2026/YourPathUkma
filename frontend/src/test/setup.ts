// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test.
import "@testing-library/jest-dom/vitest";
import { setFetch } from "../api/client";
import { setAccessToken } from "../api/token";
import { resetMockDb } from "../mocks/db";
import { server } from "../mocks/server";

// У Node `fetch` не приймає відносних адрес, тож для тестів резолвимо їх відносно localhost.
const relativeFetch: typeof fetch = (input, init) =>
  globalThis.fetch(new URL(String(input), "http://localhost"), init);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => setFetch(relativeFetch));
afterEach(() => {
  server.resetHandlers();
  resetMockDb();
  setAccessToken(null);
});
afterAll(() => server.close());
