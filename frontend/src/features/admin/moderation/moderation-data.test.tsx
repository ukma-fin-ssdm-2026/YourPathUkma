// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { setAccessToken } from "../../../api/token";
import { db } from "../../../mocks/db";
import { server } from "../../../mocks/server";
import { moderationItemFixture } from "../../../test/handlers";
import { describeDiff, useBulkReview, useModerationItems, useReviewItem } from "./useModeration";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => setAccessToken("t"));

describe("describeDiff", () => {
  it("для зміни показує «поле: старе → нове»", () => {
    const item = moderationItemFixture({
      diff: { credits: { old: 5, new: 4 }, title: { old: "А", new: "Б" } },
    });
    expect(describeDiff(item)).toEqual(["credits: 5 → 4", "title: А → Б"]);
  });

  it("для додавання й видалення показує поля payload", () => {
    const add = moderationItemFixture({
      change_type: "add",
      diff: null,
      payload: { title: "Нова", credits: 4 },
    });
    expect(describeDiff(add)).toEqual(["title: Нова", "credits: 4"]);
    const remove = moderationItemFixture({
      change_type: "remove",
      diff: null,
      payload: { title: "Стара" },
    });
    expect(describeDiff(remove)).toEqual(["title: Стара"]);
  });

  it("значення-об'єкти та HTML лишаються текстом", () => {
    const item = moderationItemFixture({
      diff: { tags: { old: { a: 1 }, new: "<b>x</b>" } },
    });
    expect(describeDiff(item)).toEqual(['tags: {"a":1} → <b>x</b>']);
  });
});

describe("useModerationItems", () => {
  it("за замовчуванням просить записи зі статусом pending", async () => {
    let seen: URL | undefined;
    server.use(
      http.get("*/api/v1/admin/moderation-items", ({ request }) => {
        seen = new URL(request.url);
        return HttpResponse.json({
          moderation_items: [],
          pagination: { limit: 20, offset: 0, total: 0, has_more: false },
        });
      }),
    );
    const { result } = renderHook(() => useModerationItems({ page: 1 }), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(seen?.searchParams.get("status")).toBe("pending");
    expect(seen?.searchParams.get("limit")).toBe("20");
    expect(seen?.searchParams.get("offset")).toBe("0");
    expect(seen?.searchParams.has("change_type")).toBe(false);
  });

  it("мок фільтрує за типом зміни", async () => {
    const { result } = renderHook(() => useModerationItems({ page: 1, changeType: "add" }), {
      wrapper,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data!.moderation_items.length).toBeGreaterThan(0);
    expect(result.current.data!.moderation_items.every((i) => i.change_type === "add")).toBe(true);
  });
});

describe("useReviewItem", () => {
  it("схвалення не має тіла, відхилення передає причину лише коли вона задана", async () => {
    const bodies: unknown[] = [];
    server.use(
      http.post("*/api/v1/admin/moderation-items/:id/:decision", async ({ request, params }) => {
        bodies.push([params.decision, await request.text()]);
        return HttpResponse.json(moderationItemFixture({ status: "approved" }));
      }),
    );
    const { result } = renderHook(() => useReviewItem(), { wrapper });
    await result.current.mutateAsync({ id: 501, decision: "approve" });
    await result.current.mutateAsync({ id: 501, decision: "reject", reason: "Помилка парсингу" });
    await result.current.mutateAsync({ id: 501, decision: "reject" });
    expect(bodies).toEqual([
      ["approve", ""],
      ["reject", '{"reason":"Помилка парсингу"}'],
      ["reject", ""],
    ]);
  });

  it("повторне рішення дає 409 MODERATION_ITEM_ALREADY_REVIEWED", async () => {
    const { result } = renderHook(() => useReviewItem(), { wrapper });
    await result.current.mutateAsync({ id: 501, decision: "approve" });
    await expect(result.current.mutateAsync({ id: 501, decision: "reject" })).rejects.toMatchObject(
      {
        status: 409,
        code: "MODERATION_ITEM_ALREADY_REVIEWED",
      },
    );
    expect(db.admin.moderationItems.find((i) => i.id === 501)?.status).toBe("approved");
  });
});

describe("useBulkReview", () => {
  it("повертає схвалені й пропущені", async () => {
    const { result } = renderHook(() => useBulkReview(), { wrapper });
    const review = renderHook(() => useReviewItem(), { wrapper });
    await review.result.current.mutateAsync({ id: 502, decision: "reject" });
    const outcome = await result.current.mutateAsync({ item_ids: [501, 502], decision: "approve" });
    expect(outcome).toEqual({
      approved: [501],
      rejected: [],
      skipped: [{ id: 502, code: "MODERATION_ITEM_ALREADY_REVIEWED" }],
    });
  });

  it("мок відхиляє порожній список і понад 100 записів", async () => {
    const { result } = renderHook(() => useBulkReview(), { wrapper });
    await expect(
      result.current.mutateAsync({ item_ids: [], decision: "approve" }),
    ).rejects.toMatchObject({
      status: 422,
    });
    await expect(
      result.current.mutateAsync({
        item_ids: Array.from({ length: 101 }, (_, i) => i + 1),
        decision: "approve",
      }),
    ).rejects.toMatchObject({ status: 422 });
  });
});
