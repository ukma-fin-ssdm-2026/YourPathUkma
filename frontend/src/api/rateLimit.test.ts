// Використання ШІ: файл створено за допомогою Antigravity (Gemini 4 Hydrogen) для перевірки Retry-After та retry-політики (#298).
// Перевірка: npx vitest run src/api/rateLimit.test.ts.
import { afterEach, describe, expect, it } from "vitest";
import { request, setFetch } from "./client";
import { ApiError, formatRetryAfter } from "./errors";
import { shouldRetryQuery } from "./queryClient";

describe("rate limit frontend handling", () => {
  afterEach(() => {
    setFetch(fetch);
  });

  it("parses Retry-After header into ApiError on 429", async () => {
    setFetch(async () =>
      new Response(
        JSON.stringify({ code: "RATE_LIMITED", message: "Забагато запитів", details: [], request_id: "req_1" }),
        { status: 429, headers: { "Content-Type": "application/json", "Retry-After": "45" } },
      ),
    );

    let caught: unknown;
    try {
      await request("/directions", { auth: false });
    } catch (err) {
      caught = err;
    }

    expect(caught).toBeInstanceOf(ApiError);
    const apiErr = caught as ApiError;
    expect(apiErr.status).toBe(429);
    expect(apiErr.code).toBe("RATE_LIMITED");
    expect(apiErr.retryAfter).toBe(45);
  });

  it("formats Retry-After seconds into human-readable Ukrainian strings", () => {
    expect(formatRetryAfter(null)).toBeNull();
    expect(formatRetryAfter(0)).toBeNull();
    expect(formatRetryAfter(45)).toBe("через 45 с");
    expect(formatRetryAfter(125)).toBe("через 3 хв");
    expect(formatRetryAfter(3600)).toBe("через 1 год");
  });

  it("does not retry 429 or other 4xx errors in QueryClient", () => {
    const err429 = new ApiError(429, "RATE_LIMITED", "Too many requests", [], null, 30);
    const err404 = new ApiError(404, "NOT_FOUND", "Not found");
    const err500 = new ApiError(500, "INTERNAL_ERROR", "Server error");

    expect(shouldRetryQuery(0, err429)).toBe(false);
    expect(shouldRetryQuery(0, err404)).toBe(false);
    expect(shouldRetryQuery(0, err500)).toBe(true);
    expect(shouldRetryQuery(2, err500)).toBe(false);
  });
});
