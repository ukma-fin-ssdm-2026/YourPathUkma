// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: directions.test.tsx.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { request } from "../../../api/client";
import type { ApiError } from "../../../api/errors";
import type { Direction, DirectionInput } from "../../../api/types";

/** POST без `id`, PATCH з `id`. Список напрямків (✅ GET /directions) оновлюється після успіху. */
export function useSaveDirection() {
  const queryClient = useQueryClient();
  return useMutation<Direction, ApiError, { id?: number; input: Partial<DirectionInput> }>({
    mutationFn: ({ id, input }) =>
      request<Direction>(id === undefined ? "/admin/directions" : `/admin/directions/${id}`, {
        method: id === undefined ? "POST" : "PATCH",
        body: input,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["directions"] }),
  });
}

export function useDeleteDirection() {
  const queryClient = useQueryClient();
  return useMutation<void, ApiError, number>({
    mutationFn: (id) => request(`/admin/directions/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["directions"] }),
  });
}
