// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тест спершу впав).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { setFetch } from "./client";
import { useConfig } from "./config";

describe("useConfig", () => {
  it("завантажує /config без автентифікації", async () => {
    const body = { api_version: "1.0.0", limits: { total_credits: 240 } };
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } }),
      );
    setFetch(fetchMock);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useConfig(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.limits.total_credits).toBe(240);
    expect(String(fetchMock.mock.calls[0]![0])).toBe("/api/v1/config");
    expect(
      new Headers((fetchMock.mock.calls[0]![1] as RequestInit).headers).has("Authorization"),
    ).toBe(false);
  });
});
