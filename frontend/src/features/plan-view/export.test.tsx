// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { setAccessToken } from "../../api/token";
import { server } from "../../mocks/server";
import { useExportPlan } from "./useExportPlan";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const saved: string[] = [];
let click: { mockRestore: () => void };

beforeEach(() => {
  setAccessToken("t");
  saved.length = 0;
  Object.assign(URL, { createObjectURL: vi.fn(() => "blob:test"), revokeObjectURL: vi.fn() });
  click = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(function (this: HTMLAnchorElement) {
      saved.push(this.download);
    });
});
afterEach(() => click.mockRestore());

describe("useExportPlan", () => {
  it("запитує PDF і зберігає файл з іменем із відповіді", async () => {
    const urls: URL[] = [];
    server.use(
      http.get("*/api/v1/plans/:id/export", ({ request }) => {
        urls.push(new URL(request.url));
        return new HttpResponse("%PDF-1.4", {
          headers: {
            "Content-Type": "application/pdf",
            "Content-Disposition": 'attachment; filename="moy-plan.pdf"',
          },
        });
      }),
    );
    const { result } = renderHook(() => useExportPlan(), { wrapper });
    let name = "";
    await act(async () => {
      name = await result.current.mutateAsync({ id: 3, academicYear: 2026 });
    });
    expect(urls[0]!.searchParams.get("format")).toBe("pdf");
    expect(name).toBe("moy-plan.pdf");
    expect(saved).toEqual(["moy-plan.pdf"]);
  });

  it("без Content-Disposition бере запасне ім'я plan-<рік>.pdf", async () => {
    server.use(
      http.get(
        "*/api/v1/plans/:id/export",
        () => new HttpResponse("%PDF-1.4", { headers: { "Content-Type": "application/pdf" } }),
      ),
    );
    const { result } = renderHook(() => useExportPlan(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ id: 3, academicYear: 2026 });
    });
    expect(saved).toEqual(["plan-2026.pdf"]);
  });

  it("мок за замовчуванням віддає plan-2026.pdf", async () => {
    const { result } = renderHook(() => useExportPlan(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ id: 3, academicYear: 2026 });
    });
    expect(saved).toEqual(["plan-2026.pdf"]);
  });

  it("помилка сервера: ApiError, файл не зберігається", async () => {
    server.use(
      http.get("*/api/v1/plans/:id/export", () =>
        HttpResponse.json({ code: "PLAN_NOT_FOUND", message: "x", details: [] }, { status: 404 }),
      ),
    );
    const { result } = renderHook(() => useExportPlan(), { wrapper });
    await act(async () => {
      await expect(result.current.mutateAsync({ id: 9, academicYear: 2026 })).rejects.toMatchObject({
        status: 404,
        code: "PLAN_NOT_FOUND",
      });
    });
    expect(saved).toEqual([]);
  });
});
