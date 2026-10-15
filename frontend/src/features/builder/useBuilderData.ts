// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: data.test.tsx.
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "../../api/client";
import type { ApiError } from "../../api/errors";
import type { PlanResponse, PlanValidationResponse } from "../../api/types";
import { useDebouncedValue } from "../catalog/useDebouncedValue";
import type { BuilderPlan } from "./plan";

/**
 * Тіло, яке приймають POST /plans, PUT /plans/{id} і POST /plans/validate.
 * Для 4 курсу навантаження бекенд вираховує сам і відхиляє load_levels (LOAD_LEVELS_NOT_ALLOWED).
 */
export function planPayload(plan: BuilderPlan) {
  const { load_levels, ...rest } = {
    academic_year: plan.academic_year,
    course: plan.course,
    load_levels: plan.load_levels,
    items: plan.items,
  };
  return plan.course === 4 ? rest : { ...rest, load_levels };
}

/**
 * Живі перевірки плану. Результат ключується вмістом плану, тож повільна відповідь на старий стан
 * не перезаписує свіжу. Порожній план бекенд відхиляє (items від 1), тому для нього запиту немає.
 */
export function useValidatePlan(plan: BuilderPlan, options: { debounceMs?: number } = {}) {
  const settled = useDebouncedValue(plan, options.debounceMs ?? 400);
  return useQuery({
    queryKey: ["validate", JSON.stringify(planPayload(settled))],
    queryFn: ({ signal }) =>
      request<PlanValidationResponse>("/plans/validate", { method: "POST", body: planPayload(settled), signal }),
    enabled: settled.items.length > 0,
    placeholderData: keepPreviousData,
  });
}

export function usePlan(id: number | null) {
  return useQuery({
    queryKey: ["plan", id],
    queryFn: () => request<PlanResponse>(`/plans/${id}`),
    enabled: id !== null,
  });
}

/** Новий план це POST, наявний (є id) це PUT з повною заміною. */
export function useSavePlan() {
  const queryClient = useQueryClient();
  return useMutation<PlanResponse, ApiError, { id: number | null; plan: BuilderPlan }>({
    mutationFn: ({ id, plan }) =>
      id === null
        ? request<PlanResponse>("/plans", { method: "POST", body: planPayload(plan) })
        : request<PlanResponse>(`/plans/${id}`, { method: "PUT", body: planPayload(plan) }),
    onSuccess: (saved) => {
      queryClient.setQueryData(["plan", saved.id], saved);
      void queryClient.invalidateQueries({ queryKey: ["plans"] });
    },
  });
}

export function useSubmitPlan() {
  const queryClient = useQueryClient();
  return useMutation<PlanResponse, ApiError, number>({
    mutationFn: (id) => request<PlanResponse>(`/plans/${id}/submit`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["plans"] }),
  });
}
