// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: preferences-data.test.tsx.
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
    mutationFn: (input) => request<Preferences>(`/preferences/${year}`, { method: "PUT", body: input }),
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
    queryKey: ["instructors", term],
    queryFn: () => request<InstructorsPage>("/instructors", { query: { q: term, limit: 10 } }),
    enabled: term.length >= 2,
  });
}

/** Словник id → ПІБ для підписів збережених викладачів (перші 100 з довідника). */
export function useInstructorNames(): Map<number, string> {
  const query = useQuery({
    queryKey: ["instructors", "all"],
    queryFn: () => request<InstructorsPage>("/instructors", { query: { limit: 100 } }),
    staleTime: 5 * 60 * 1000,
  });
  return useMemo(
    () => new Map((query.data?.instructors ?? []).map((item) => [item.id, item.full_name])),
    [query.data],
  );
}
