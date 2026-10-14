// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: config.test.tsx.
import { useQuery } from "@tanstack/react-query";
import { request } from "./client";
import type { ConfigResponse } from "./types";

const FIVE_MINUTES = 5 * 60 * 1000;

export function useConfig() {
  return useQuery({
    queryKey: ["config"],
    queryFn: () => request<ConfigResponse>("/config", { auth: false }),
    staleTime: FIVE_MINUTES,
  });
}
