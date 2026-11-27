// Використання ШІ: Codex додав регресії #220; перевірка: Vitest red/green.
import { request, requestBlob, setFetch } from "./client";
import { ApiError } from "./errors";
import { shouldRetryQuery } from "./queryClient";
import { formatDateTime } from "../lib/datetime";
import { signOut, useSession } from "../auth/session";

it("wraps malformed successful JSON with request ID", async () => {
  setFetch(
    vi.fn().mockResolvedValue(new Response("<html>", { headers: { "X-Request-ID": "bad-json" } })),
  );
  await expect(request("/me")).rejects.toMatchObject({
    code: "BAD_RESPONSE",
    requestId: "bad-json",
  });
});
it.each([500, 502, 503])("hides server details for %s", async (status) => {
  setFetch(
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          code: "INTERNAL",
          message: "secret SQL",
          details: [{ field: "x", message: "secret" }],
        }),
        { status, headers: { "X-Request-ID": "safe" } },
      ),
    ),
  );
  const error = (await request("/me").catch((e: unknown) => e)) as ApiError;
  expect(error).toBeInstanceOf(ApiError);
  expect(error.message).not.toContain("secret");
  expect(error.details).toEqual([]);
  expect(error.requestId).toBe("safe");
});
it("returns an explicit failed logout result while clearing session", async () => {
  setFetch(vi.fn().mockRejectedValue(new TypeError("offline")));
  await expect(signOut()).resolves.toBe(false);
  expect(useSession.getState().status).toBe("anonymous");
});
it("returns a confirmed logout result", async () => {
  setFetch(vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
  await expect(signOut()).resolves.toBe(true);
});
it("preserves caller cancellation", async () => {
  const controller = new AbortController();
  controller.abort();
  setFetch(vi.fn().mockRejectedValue(new DOMException("cancelled", "AbortError")));
  await expect(request("/me", { signal: controller.signal })).rejects.toMatchObject({
    name: "AbortError",
  });
});
it.each([null, "", "invalid", "2026-99-99"])("handles invalid date %s", (value) => {
  expect(formatDateTime(value)).toBe("—");
});
it.each([401, 403, 404, 422, 429])("does not retry %s", (status) => {
  expect(shouldRetryQuery(0, new ApiError(status, "ERROR", "error"))).toBe(false);
});
it("bounds retries for temporary errors", () => {
  expect(shouldRetryQuery(0, new ApiError(503, "ERROR", "error"))).toBe(true);
  expect(shouldRetryQuery(2, new ApiError(503, "ERROR", "error"))).toBe(false);
});

it.each(["json", "blob"] as const)("cancels %s after response headers arrive", async (kind) => {
  const controller = new AbortController();
  let reading = false;
  setFetch(async (_url, init) => {
    const response = new Response();
    Object.defineProperty(response, kind, {
      value: () => {
        reading = true;
        return new Promise((_resolve, reject) =>
          init?.signal?.addEventListener(
            "abort",
            () => reject(new DOMException("cancelled", "AbortError")),
            { once: true },
          ),
        );
      },
    });
    return response;
  });
  const pending = (
    kind === "json"
      ? request("/me", { signal: controller.signal })
      : requestBlob("/export", { signal: controller.signal })
  ).catch((error: unknown) => error);
  await vi.waitFor(() => expect(reading).toBe(true));
  controller.abort();
  expect(await pending).toMatchObject({ name: "AbortError" });
});

it.each(["json", "blob"] as const)("classifies %s body timeout after headers", async (kind) => {
  vi.useFakeTimers();
  try {
    setFetch(async (_url, init) => {
      const response = new Response();
      Object.defineProperty(response, kind, {
        value: () =>
          new Promise((_resolve, reject) =>
            init?.signal?.addEventListener(
              "abort",
              () => reject(new DOMException("timeout", "AbortError")),
              { once: true },
            ),
          ),
      });
      return response;
    });
    const pending = (
      kind === "json"
        ? request("/me", { timeoutMs: 1000 })
        : requestBlob("/export", { timeoutMs: 1000 })
    ).catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(1000);
    expect(await pending).toMatchObject({ status: 0, code: "TIMEOUT" });
  } finally {
    vi.useRealTimers();
  }
});
