// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { http, HttpResponse } from "msw";
import type { PlanItem, PlanResponse } from "../../api/types";
import { setAccessToken } from "../../api/token";
import { server } from "../../mocks/server";
import { planFixture, plansCrudHandlers, validateHandler } from "../../test/handlers";
import type { BuilderPlan } from "./plan";
import {
  planPayload,
  usePlan,
  useSavePlan,
  useSubmitPlan,
  useValidatePlan,
} from "./useBuilderData";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const item = (id: number, credits = 5, free = false): PlanItem => ({
  course_id: id,
  title: `Дисципліна ${id}`,
  trimester: 1,
  credits,
  is_free_elective: free,
});

const planWith = (items: PlanItem[]): BuilderPlan => ({
  academic_year: 2026,
  course: 3,
  load_levels: { autumn: "medium", spring: "medium", summer: "medium" },
  items,
});

beforeEach(() => setAccessToken("t"));

describe("planPayload", () => {
  it("для 4 курсу не надсилає load_levels: бекенд сам вираховує навантаження", () => {
    const body = planPayload({ ...planWith([item(1)]), course: 4 });
    expect(body).not.toHaveProperty("load_levels");
  });

  it("для інших курсів надсилає load_levels", () => {
    expect(planPayload(planWith([item(1)]))).toHaveProperty("load_levels");
  });
});

describe("useValidatePlan", () => {
  it("порожній план не робить запиту", () => {
    let calls = 0;
    server.use(validateHandler(() => (calls += 1)));
    const { result } = renderHook(() => useValidatePlan(planWith([]), { debounceMs: 5 }), {
      wrapper,
    });
    expect(result.current.fetchStatus).toBe("idle");
    expect(calls).toBe(0);
  });

  it("план з елементами повертає summary й шле лише поля PlanPayload", async () => {
    const bodies: unknown[] = [];
    server.use(validateHandler((body) => bodies.push(body)));
    const { result } = renderHook(
      () => useValidatePlan(planWith([item(1, 5), item(2, 3, true)]), { debounceMs: 5 }),
      {
        wrapper,
      },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.summary).toMatchObject({
      total_credits: 8,
      free_elective_credits: 3,
    });
    expect(Object.keys(bodies[0] as object).sort()).toEqual([
      "academic_year",
      "course",
      "items",
      "load_levels",
    ]);
  });

  it("перевищення вільного вибору дає помилку FREE_ELECTIVE_LIMIT_EXCEEDED", async () => {
    server.use(validateHandler());
    const { result } = renderHook(
      () => useValidatePlan(planWith([item(1, 5), item(2, 26, true)]), { debounceMs: 5 }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.valid).toBe(false);
    expect(result.current.data?.errors.map((e) => e.code)).toContain(
      "FREE_ELECTIVE_LIMIT_EXCEEDED",
    );
  });

  it("застаріла повільна відповідь не перезаписує свіжу", async () => {
    // Перший запит (1 елемент) відповідає за 250 мс, другий (2 елементи) майже одразу.
    server.use(validateHandler(undefined, (body) => (body.items.length === 1 ? 250 : 5)));
    const { result, rerender } = renderHook(
      ({ plan }) => useValidatePlan(plan, { debounceMs: 5 }),
      {
        wrapper,
        initialProps: { plan: planWith([item(1, 5)]) },
      },
    );
    await new Promise((resolve) => setTimeout(resolve, 40));
    rerender({ plan: planWith([item(1, 5), item(2, 6)]) });
    await waitFor(() => expect(result.current.data?.summary.total_credits).toBe(11));
    await new Promise((resolve) => setTimeout(resolve, 350));
    expect(result.current.data?.summary.total_credits).toBe(11);
  });
});

describe("usePlan / useSavePlan / useSubmitPlan", () => {
  it("usePlan завантажує план, а відсутній дає 404", async () => {
    const crud = plansCrudHandlers([planFixture({ id: 1 })]);
    server.use(...crud.handlers);
    const found = renderHook(() => usePlan(1), { wrapper });
    await waitFor(() => expect(found.result.current.data?.id).toBe(1));
    const missing = renderHook(() => usePlan(99), { wrapper });
    await waitFor(() =>
      expect(missing.result.current.error).toMatchObject({ status: 404, code: "PLAN_NOT_FOUND" }),
    );
  });

  it("перше збереження це POST, наступне з тим самим id це PUT", async () => {
    const crud = plansCrudHandlers();
    server.use(...crud.handlers);
    const { result } = renderHook(() => useSavePlan(), { wrapper });
    let first: PlanResponse | undefined;
    await act(async () => {
      first = await result.current.mutateAsync({ id: null, plan: planWith([item(1)]) });
    });
    expect(first).toMatchObject({ status: "draft", total_credits: 5 });
    await act(async () => {
      await result.current.mutateAsync({ id: first!.id, plan: planWith([item(1), item(2)]) });
    });
    expect(crud.calls).toMatchObject({ post: 1, put: 1 });
  });

  it("PUT чужого статусу дає 409 PLAN_NOT_EDITABLE", async () => {
    const crud = plansCrudHandlers([planFixture({ id: 3, status: "submitted" })]);
    server.use(...crud.handlers);
    const { result } = renderHook(() => useSavePlan(), { wrapper });
    await act(async () => {
      await expect(
        result.current.mutateAsync({ id: 3, plan: planWith([item(1)]) }),
      ).rejects.toMatchObject({
        status: 409,
        code: "PLAN_NOT_EDITABLE",
      });
    });
  });

  it("подання повертає план зі статусом submitted", async () => {
    const { result } = renderHook(() => useSubmitPlan(), { wrapper });
    await act(async () => {
      const submitted = await result.current.mutateAsync(5);
      expect(submitted).toMatchObject({ id: 5, status: "submitted" });
    });
  });

  it("помилка 409 PLAN_NOT_SUBMITTABLE пробрасується", async () => {
    server.use(
      http.post("*/api/v1/plans/:id/submit", () =>
        HttpResponse.json(
          { code: "PLAN_NOT_SUBMITTABLE", message: "x", details: [] },
          { status: 409 },
        ),
      ),
    );
    const { result } = renderHook(() => useSubmitPlan(), { wrapper });
    await act(async () => {
      await expect(result.current.mutateAsync(5)).rejects.toMatchObject({
        code: "PLAN_NOT_SUBMITTABLE",
      });
    });
  });
});
