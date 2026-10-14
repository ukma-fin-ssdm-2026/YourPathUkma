// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: onboarding.test.tsx.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "../../api/client";
import type { ApiError } from "../../api/errors";
import type { Me } from "../../api/types";
import { useSession } from "../../auth/session";

export const ME_KEY = ["me"] as const;

export function useMe() {
  const authenticated = useSession((s) => s.status === "authenticated");
  return useQuery({
    queryKey: ME_KEY,
    queryFn: () => request<Me>("/me"),
    enabled: authenticated,
  });
}

export interface OnboardingInput {
  course_year: 1 | 2 | 3 | 4;
  specialty: string;
}

export function useOnboard() {
  const queryClient = useQueryClient();
  return useMutation<Me, ApiError, OnboardingInput>({
    mutationFn: (input) => request<Me>("/me/onboarding", { method: "POST", body: input }),
    onSuccess: (me) => queryClient.setQueryData(ME_KEY, me),
  });
}
