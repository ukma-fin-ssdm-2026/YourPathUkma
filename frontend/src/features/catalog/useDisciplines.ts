// Використання ШІ: Codex виправив #220; перевірка: регресії Vitest, ESLint і TypeScript.
// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: catalog-data.test.tsx.
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { request } from "../../api/client";
import type { Direction, PaginatedDisciplinesResponse } from "../../api/types";
import { disciplinesQuery, type DisciplineFilters } from "./filters";

export function useDisciplines(filters: DisciplineFilters, page: number) {
  return useQuery({
    queryKey: ["disciplines", filters, page],
    queryFn: ({ signal }) =>
      request<PaginatedDisciplinesResponse>("/disciplines", {
        signal,
        query: disciplinesQuery(filters, page),
      }),
    placeholderData: keepPreviousData,
  });
}

export function useDirections() {
  return useQuery({
    queryKey: ["directions"],
    queryFn: ({ signal }) => request<{ directions: Direction[] }>("/directions", { signal }),
    staleTime: 5 * 60 * 1000,
  });
}
