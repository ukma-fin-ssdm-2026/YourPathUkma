// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { setAccessToken } from "../../api/token";
import { server } from "../../mocks/server";
import { instructorsHandler } from "../../test/handlers";
import {
  MAX_DIRECTIONS,
  defaultPreferences,
  hasLowLoad,
  moveInstructor,
  toggleDirection,
} from "./preferences";
import { useInstructorNames, useInstructors, usePreferences, useSavePreferences } from "./usePreferences";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => setAccessToken("t"));

describe("чисті функції побажань", () => {
  it("toggleDirection додає, знімає й не перевищує ліміт", () => {
    expect(MAX_DIRECTIONS).toBe(3);
    expect(toggleDirection([1, 2], 3)).toEqual([1, 2, 3]);
    expect(toggleDirection([1, 2, 3], 4)).toEqual([1, 2, 3]);
    expect(toggleDirection([1, 2], 1)).toEqual([2]);
    expect(toggleDirection([1, 2, 3], 2)).toEqual([1, 3]);
  });

  it("moveInstructor переносить між списками без дубліката", () => {
    const base = { preferred_instructor_ids: [7], unwanted_instructor_ids: [12] };
    expect(moveInstructor(base, 7, "unwanted")).toEqual({
      preferred_instructor_ids: [],
      unwanted_instructor_ids: [12, 7],
    });
    expect(moveInstructor(base, 12, "preferred")).toEqual({
      preferred_instructor_ids: [7, 12],
      unwanted_instructor_ids: [],
    });
    expect(moveInstructor(base, 7, null)).toEqual({
      preferred_instructor_ids: [],
      unwanted_instructor_ids: [12],
    });
    expect(moveInstructor(base, 7, "preferred")).toEqual(base);
  });

  it("hasLowLoad бачить низьке навантаження в будь-якому триместрі", () => {
    expect(hasLowLoad({ autumn: "medium", spring: "high", summer: "low" })).toBe(true);
    expect(hasLowLoad({ autumn: "medium", spring: "high", summer: "medium" })).toBe(false);
  });

  it("defaultPreferences: усе середнє, вільний вибір дозволено", () => {
    expect(defaultPreferences(2026)).toEqual({
      academic_year: 2026,
      load_levels: { autumn: "medium", spring: "medium", summer: "medium" },
      direction_ids: [],
      include_free_electives: true,
      preferred_instructor_ids: [],
      unwanted_instructor_ids: [],
      wants_certificate: false,
      certificate_program_id: null,
    });
  });
});

describe("usePreferences / useSavePreferences", () => {
  it("404 PREFERENCES_NOT_FOUND дає значення за замовчуванням, а не помилку", async () => {
    const { result } = renderHook(() => usePreferences(2026), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(defaultPreferences(2026));
  });

  it("збережені побажання повертаються при наступному читанні", async () => {
    const save = renderHook(() => useSavePreferences(2026), { wrapper });
    await act(async () => {
      await save.result.current.mutateAsync({ ...defaultPreferences(2026), direction_ids: [1, 2] });
    });
    const read = renderHook(() => usePreferences(2026), { wrapper });
    await waitFor(() => expect(read.result.current.data?.direction_ids).toEqual([1, 2]));
    expect(read.result.current.data?.updated_at).toBeTruthy();
  });

  it("сервер відхиляє 4 напрямки: 422 з полем direction_ids", async () => {
    const { result } = renderHook(() => useSavePreferences(2026), { wrapper });
    await act(async () => {
      await expect(
        result.current.mutateAsync({ ...defaultPreferences(2026), direction_ids: [1, 2, 3, 4] }),
      ).rejects.toMatchObject({
        status: 422,
        details: [expect.objectContaining({ field: "direction_ids" })],
      });
    });
  });

  it("сервер відхиляє викладача в обох списках: 422", async () => {
    const { result } = renderHook(() => useSavePreferences(2026), { wrapper });
    await act(async () => {
      await expect(
        result.current.mutateAsync({
          ...defaultPreferences(2026),
          preferred_instructor_ids: [7],
          unwanted_instructor_ids: [7],
        }),
      ).rejects.toMatchObject({
        status: 422,
        details: [expect.objectContaining({ field: "preferred_instructor_ids" })],
      });
    });
  });
});

describe("useInstructors / useInstructorNames", () => {
  it("менше двох символів: запиту немає", () => {
    const { result } = renderHook(() => useInstructors("а"), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("від двох символів шле q і limit=10", async () => {
    const urls: URL[] = [];
    server.use(
      instructorsHandler([{ id: 7, full_name: "Петренко І. М." }], (url) => urls.push(url)),
    );
    const { result } = renderHook(() => useInstructors("Пет"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.instructors[0]?.full_name).toBe("Петренко І. М.");
    expect(urls[0]!.searchParams.get("q")).toBe("Пет");
    expect(urls[0]!.searchParams.get("limit")).toBe("10");
  });

  it("useInstructorNames будує словник id → ПІБ", async () => {
    server.use(
      instructorsHandler([
        { id: 7, full_name: "Петренко І. М." },
        { id: 12, full_name: "Гончар В. Т." },
      ]),
    );
    const { result } = renderHook(() => useInstructorNames(), { wrapper });
    await waitFor(() => expect(result.current.size).toBe(2));
    expect(result.current.get(12)).toBe("Гончар В. Т.");
  });
});
