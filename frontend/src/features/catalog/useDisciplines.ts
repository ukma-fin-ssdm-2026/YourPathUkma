// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: catalog-data.test.tsx.
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { request } from "../../api/client";
import type { Direction, PaginatedDisciplinesResponse } from "../../api/types";
import { disciplinesQuery, type DisciplineFilters } from "./filters";

export function useDisciplines(filters: DisciplineFilters, page: number) {
  return useQuery({
    queryKey: ["disciplines", filters, page],
    queryFn: () =>
      request<PaginatedDisciplinesResponse>("/disciplines", {
        query: disciplinesQuery(filters, page),
      }),
    placeholderData: keepPreviousData,
  });
}

export function useDirections() {
  return useQuery({
    queryKey: ["directions"],
    queryFn: () => request<{ directions: Direction[] }>("/directions"),
    staleTime: 5 * 60 * 1000,
  });
}
