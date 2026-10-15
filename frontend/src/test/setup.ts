// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test.
import "@testing-library/jest-dom/vitest";
import { setFetch } from "../api/client";
import { setAccessToken } from "../api/token";
import { resetMockDb } from "../mocks/db";
import { server } from "../mocks/server";
import { encodeMultipart } from "./multipart";

// У Node `fetch` не приймає відносних адрес, тож для тестів резолвимо їх відносно localhost.
// jsdom-ний FormData Node `fetch` не розуміє, тож перекодовуємо його у звичайне multipart-тіло.
const relativeFetch: typeof fetch = async (input, init) => {
  const url = new URL(String(input), "http://localhost");
  if (init?.body instanceof FormData) {
    const { contentType, body } = await encodeMultipart(init.body);
    const headers = new Headers(init.headers);
    headers.set("Content-Type", contentType);
    return globalThis.fetch(url, { ...init, headers, body: body as unknown as BodyInit });
  }
  return globalThis.fetch(url, init);
};

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => setFetch(relativeFetch));
afterEach(() => {
  server.resetHandlers();
  resetMockDb();
  setAccessToken(null);
});
afterAll(() => server.close());
