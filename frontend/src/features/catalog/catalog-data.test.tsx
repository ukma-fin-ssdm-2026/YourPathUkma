// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { server } from "../../mocks/server";
import { directionsHandler, disciplineFixture, disciplinesHandler } from "../../test/handlers";
import { PAGE_SIZE, disciplinesQuery, filtersFromParams, paramsFromFilters } from "./filters";
import { useDebouncedValue } from "./useDebouncedValue";
import { useDirections, useDisciplines } from "./useDisciplines";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("filtersFromParams", () => {
  it("розбирає допустимі значення й сторінку", () => {
    const { filters, page } = filtersFromParams(
      new URLSearchParams("trimester=2&min_credits=3&recommended_year=3&direction=Data%20Science&page=3"),
    );
    expect(filters).toEqual({
      trimester: 2,
      min_credits: 3,
      recommended_year: 3,
      direction: "Data Science",
    });
    expect(page).toBe(3);
  });

  it("відкидає недопустимі значення", () => {
    const { filters, page } = filtersFromParams(
      new URLSearchParams("trimester=9&min_credits=abc&recommended_year=1&page=-1&direction="),
    );
    expect(filters).toEqual({});
    expect(page).toBe(1);
  });

  it("paramsFromFilters обернений до filtersFromParams, а сторінка 1 не пишеться", () => {
    const original = new URLSearchParams("trimester=2&instructor=Петренко&page=4");
    const { filters, page } = filtersFromParams(original);
    expect(paramsFromFilters(filters, page).toString()).toBe(
      new URLSearchParams("trimester=2&instructor=Петренко&page=4").toString(),
    );
    expect(paramsFromFilters(filters, 1).has("page")).toBe(false);
  });
});

describe("disciplinesQuery", () => {
  it("додає тип elective, ліміт і зсув", () => {
    expect(disciplinesQuery({ trimester: 2 }, 3)).toEqual({
      discipline_type: "elective",
      trimester: 2,
      limit: PAGE_SIZE,
      offset: 24,
    });
  });

  it("пропускає викладача коротше 2 символів, бо бекенд поверне 422", () => {
    expect(disciplinesQuery({ instructor: "а" }, 1)).not.toHaveProperty("instructor");
    expect(disciplinesQuery({ instructor: "Пе" }, 1)).toHaveProperty("instructor", "Пе");
  });

  it("не надсилає суперечливий діапазон кредитів (min > max)", () => {
    const query = disciplinesQuery({ min_credits: 6, max_credits: 3 }, 1);
    expect(query).not.toHaveProperty("min_credits");
    expect(query).not.toHaveProperty("max_credits");
  });
});

describe("useDisciplines / useDirections", () => {
  it("завантажує сторінку з потрібними параметрами", async () => {
    const urls: URL[] = [];
    server.use(
      disciplinesHandler([disciplineFixture(), disciplineFixture({ id: 102 })], {
        total: 30,
        onRequest: (url) => urls.push(url),
      }),
    );
    const { result } = renderHook(() => useDisciplines({ trimester: 2 }, 3), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.disciplines).toHaveLength(2);
    expect(result.current.data?.pagination.total).toBe(30);
    const params = urls[0]!.searchParams;
    expect(params.get("discipline_type")).toBe("elective");
    expect(params.get("trimester")).toBe("2");
    expect(params.get("limit")).toBe("12");
    expect(params.get("offset")).toBe("24");
  });

  it("повертає напрямки", async () => {
    server.use(directionsHandler(["Data Science", "Cybersecurity"]));
    const { result } = renderHook(() => useDirections(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.directions.map((d) => d.name)).toEqual(["Data Science", "Cybersecurity"]);
  });
});

describe("useDebouncedValue", () => {
  afterEach(() => vi.useRealTimers());

  it("оновлює значення лише через затримку", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 300), {
      initialProps: { value: "а" },
    });
    rerender({ value: "ab" });
    act(() => void vi.advanceTimersByTime(299));
    expect(result.current).toBe("а");
    act(() => void vi.advanceTimersByTime(1));
    expect(result.current).toBe("ab");
  });
});
