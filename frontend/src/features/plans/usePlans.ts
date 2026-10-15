// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: plans.test.tsx.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "../../api/client";
import type { ApiError } from "../../api/errors";
import type { PaginatedPlansResponse, PlanResponse } from "../../api/types";

export function usePlans(status?: PlanResponse["status"]) {
  return useQuery({
    queryKey: ["plans", status ?? "all"],
    queryFn: () => request<PaginatedPlansResponse>("/plans", { query: { limit: 100, status } }),
  });
}

export function useDeletePlan() {
  const queryClient = useQueryClient();
  return useMutation<void, ApiError, number>({
    mutationFn: (id) => request(`/plans/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["plans"] }),
  });
}
