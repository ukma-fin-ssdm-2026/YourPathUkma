// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: audit.test.tsx.
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { request } from "../../../api/client";
import type { AuditLogEntry, PaginationInfo } from "../../../api/types";

export const AUDIT_PAGE_SIZE = 50;

export type AuditOutcome = AuditLogEntry["outcome"];

export const outcomeLabel = (outcome: AuditOutcome) =>
  outcome === "allowed" ? "Дозволено" : "Відмовлено";

export function useAuditLog({
  action,
  outcome,
  page,
}: {
  action: string;
  outcome?: AuditOutcome;
  page: number;
}) {
  return useQuery({
    queryKey: ["admin", "audit", action, outcome ?? "all", page],
    placeholderData: keepPreviousData,
    queryFn: () =>
      request<{ audit_log: AuditLogEntry[]; pagination: PaginationInfo }>("/admin/audit-log", {
        query: {
          limit: AUDIT_PAGE_SIZE,
          offset: (page - 1) * AUDIT_PAGE_SIZE,
          action: action || undefined,
          outcome,
        },
      }),
  });
}

/** Повний запис із `old_value`/`new_value`; завантажується лише для розгорнутого рядка. */
export function useAuditEntry(id: number | null) {
  return useQuery({
    queryKey: ["admin", "audit-entry", id],
    queryFn: () => request<AuditLogEntry>(`/admin/audit-log/${id}`),
    enabled: id !== null,
  });
}
