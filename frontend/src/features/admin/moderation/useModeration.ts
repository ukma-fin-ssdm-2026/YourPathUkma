// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: moderation-data.test.tsx.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "../../../api/client";
import type { ApiError } from "../../../api/errors";
import type { BulkReviewResult, ModerationItem, PaginationInfo } from "../../../api/types";

export const MODERATION_PAGE_SIZE = 20;

export type ModerationStatus = ModerationItem["status"];
export type ChangeType = ModerationItem["change_type"];
export type Decision = "approve" | "reject";

interface ModerationResponse {
  moderation_items: ModerationItem[];
  pagination: PaginationInfo;
}

export function useModerationItems({
  status = "pending",
  changeType,
  page,
}: {
  status?: ModerationStatus;
  changeType?: ChangeType;
  page: number;
}) {
  return useQuery({
    queryKey: ["admin", "moderation", status, changeType ?? "all", page],
    queryFn: () =>
      request<ModerationResponse>("/admin/moderation-items", {
        query: {
          limit: MODERATION_PAGE_SIZE,
          offset: (page - 1) * MODERATION_PAGE_SIZE,
          status,
          change_type: changeType,
        },
      }),
  });
}

export function useReviewItem() {
  const queryClient = useQueryClient();
  return useMutation<
    ModerationItem,
    ApiError,
    { id: number; decision: Decision; reason?: string }
  >({
    mutationFn: ({ id, decision, reason }) =>
      request<ModerationItem>(`/admin/moderation-items/${id}/${decision}`, {
        method: "POST",
        body: decision === "reject" && reason ? { reason } : undefined,
      }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["admin", "moderation"] }),
  });
}

export function useBulkReview() {
  const queryClient = useQueryClient();
  return useMutation<BulkReviewResult, ApiError, { item_ids: number[]; decision: Decision }>({
    mutationFn: (body) =>
      request<BulkReviewResult>("/admin/moderation-items/bulk-review", { method: "POST", body }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["admin", "moderation"] }),
  });
}

const show = (value: unknown): string => (typeof value === "object" ? JSON.stringify(value) : String(value));

/** Рядки зміни для відображення текстом: для update «поле: старе → нове», інакше поля payload. */
export function describeDiff(item: ModerationItem): string[] {
  if (item.diff) {
    return Object.entries(item.diff).map(([field, { old, new: next }]) => `${field}: ${show(old)} → ${show(next)}`);
  }
  return Object.entries(item.payload).map(([field, value]) => `${field}: ${show(value)}`);
}
