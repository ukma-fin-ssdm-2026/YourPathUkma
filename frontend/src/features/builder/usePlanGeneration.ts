// Використання ШІ: Codex підключив запуск і опитування API. Перевірка: Vitest і Chromium.
// Використання ШІ: Antigravity (Gemini 4 Hydrogen) додав форматування Retry-After (#298). Перевірка: Vitest.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "../../api/client";
import { ApiError, formatRetryAfter } from "../../api/errors";
import type { PlanGeneration, Preferences } from "../../api/types";

export function usePlanGeneration(scope: string, enabled: boolean) {
  const client = useQueryClient();
  const start = useMutation({
    retry: false,
    mutationFn: ({ preferences }: { scope: string; preferences: Preferences }) => {
      const {
        academic_year, load_levels, direction_ids, include_free_electives,
        preferred_instructor_ids, unwanted_instructor_ids, wants_certificate, certificate_program_id,
      } = preferences;
      return request<PlanGeneration>("/plan-generations", {
        method: "POST",
        body: {
          academic_year, load_levels, direction_ids, include_free_electives,
          preferred_instructor_ids, unwanted_instructor_ids, wants_certificate, certificate_program_id,
        },
      });
    },
  });
  const initial = enabled && start.variables?.scope === scope ? start.data : undefined;
  const status = useQuery({
    queryKey: ["plan-generation", initial?.id],
    queryFn: ({ signal }) => request<PlanGeneration>(`/plan-generations/${initial!.id}`, { signal }),
    enabled: initial?.status === "pending",
    initialData: initial,
    staleTime: Infinity,
    retry: false,
    refetchOnReconnect: false,
    refetchOnWindowFocus: false,
    refetchInterval: ({ state }) =>
      state.data?.status === "pending" && !state.error ? 3000 : false,
    refetchIntervalInBackground: false,
  });
  const generation = initial ? status.data : undefined;

  function launch(preferences: Preferences) {
    if (start.isPending || generation?.status === "pending") return;
    start.mutate({ scope, preferences });
  }

  function openDraft(onOpen: (id: number) => void) {
    if (!generation?.plan_id) return;
    void client.invalidateQueries({ queryKey: ["plans"] });
    onOpen(generation.plan_id);
  }

  return {
    generation,
    launch,
    openDraft,
    starting: start.isPending,
    startError: start.variables?.scope === scope ? start.error : null,
    statusError: initial ? status.error : null,
    checking: status.isFetching,
    checkStatus: status.refetch,
  };
}

export function generationStartError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) return "Генерація вже триває. Спробуйте пізніше.";
    if (error.status === 429) {
      const wait = formatRetryAfter(error.retryAfter);
      return wait
        ? `Вичерпано добовий ліміт генерацій. Спробуйте ${wait}.`
        : "Вичерпано добовий ліміт генерацій. Спробуйте завтра.";
    }
    if (error.status === 422) return "Перевірте побажання на обраний навчальний рік.";
  }
  return "Не вдалося запустити генерацію. Спробуйте ще раз.";
}
