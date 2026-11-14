// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: preferences-data.test.tsx.
// Codex вніс зміни для issue #221. Перевірка: фронтенд-тести й лінтер.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { request } from "../../api/client";
import { ApiError } from "../../api/errors";
import type { Instructor, PaginationInfo, Preferences } from "../../api/types";
import { defaultPreferences } from "./preferences";

export type PreferencesInput = Omit<Preferences, "updated_at">;

export function usePreferences(year: number) {
  return useQuery({
    queryKey: ["preferences", year],
    queryFn: async (): Promise<Preferences> => {
      try {
        return await request<Preferences>(`/preferences/${year}`);
      } catch (error) {
        // Побажань ще не збережено: показуємо порожню форму, а не помилку.
        if (error instanceof ApiError && error.code === "PREFERENCES_NOT_FOUND") {
          return defaultPreferences(year);
        }
        throw error;
      }
    },
  });
}

export function useSavePreferences(year: number) {
  const queryClient = useQueryClient();
  return useMutation<Preferences, ApiError, PreferencesInput>({
    mutationFn: (input) =>
      request<Preferences>(`/preferences/${year}`, { method: "PUT", body: input }),
    onSuccess: (saved) => queryClient.setQueryData(["preferences", year], saved),
  });
}

interface InstructorsPage {
  instructors: Instructor[];
  pagination: PaginationInfo;
}

/** Пошук викладача за ПІБ; бекенд приймає `q` від 2 символів. */
export function useInstructors(q: string) {
  const term = q.trim();
  return useQuery({
    queryKey: ["instructors", "search", term],
    queryFn: () => request<InstructorsPage>("/instructors", { query: { q: term, limit: 10 } }),
    enabled: term.length >= 2,
  });
}

/** Читаємо сторінки довідника, доки не знайдемо збережені імена. */
export function useInstructorNames(ids: number[]): Map<number, string> {
  const requested = [...new Set(ids)].sort((a, b) => a - b);
  const query = useQuery({
    queryKey: ["instructors", "directory", requested],
    queryFn: async ({ signal }) => {
      const missing = new Set(requested);
      const found: Instructor[] = [];
      const limit = 100;
      for (let offset = 0; missing.size > 0; offset += limit) {
        const page = await request<InstructorsPage>("/instructors", {
          query: { limit, offset },
          signal,
        });
        found.push(...page.instructors.filter((item) => missing.delete(item.id)));
        if (!page.pagination.has_more || page.instructors.length === 0) break;
      }
      return found;
    },
    enabled: requested.length > 0,
    staleTime: 5 * 60 * 1000,
  });
  return useMemo(
    () => new Map((query.data ?? []).map((item) => [item.id, item.full_name])),
    [query.data],
  );
}
