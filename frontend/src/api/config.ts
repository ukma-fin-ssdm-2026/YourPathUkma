// Використання ШІ: Codex виправив #220; перевірка: Vitest та TypeScript.
// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: config.test.tsx.
import { useQuery } from "@tanstack/react-query";
import { request } from "./client";
import type { ConfigResponse } from "./types";

const FIVE_MINUTES = 5 * 60 * 1000;

export function useConfig() {
  return useQuery({
    queryKey: ["config"],
    queryFn: ({ signal }) => request<ConfigResponse>("/config", { auth: false, signal }),
    staleTime: FIVE_MINUTES,
  });
}
