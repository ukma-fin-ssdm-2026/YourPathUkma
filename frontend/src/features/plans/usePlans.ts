// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: plans.test.tsx.
// Codex вніс зміни для issue #221. Перевірка: фронтенд-тести й лінтер.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "../../api/client";
import type { ApiError } from "../../api/errors";
import type { PaginatedPlansResponse, PlanResponse } from "../../api/types";

export const PLANS_PAGE_SIZE = 100;

export function usePlans(status: PlanResponse["status"] | undefined, page: number) {
  return useQuery({
    queryKey: ["plans", status ?? "all", page],
    queryFn: ({ signal }) =>
      request<PaginatedPlansResponse>("/plans", {
        query: { limit: PLANS_PAGE_SIZE, offset: (page - 1) * PLANS_PAGE_SIZE, status },
        signal,
      }),
  });
}

export function useDeletePlan() {
  const queryClient = useQueryClient();
  return useMutation<void, ApiError, number>({
    mutationFn: (id) => request(`/plans/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["plans"] }),
  });
}
