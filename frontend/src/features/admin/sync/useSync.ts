// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: sync.test.tsx.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "../../../api/client";
import type { ApiError } from "../../../api/errors";
import type { PaginationInfo, SyncJob } from "../../../api/types";

export const SYNC_PAGE_SIZE = 20;
export const SYNC_POLL_MS = 2000;

export type SyncSource = SyncJob["source"];

interface SyncJobsResponse {
  sync_jobs: SyncJob[];
  pagination: PaginationInfo;
}

const LABELS: Record<SyncJob["status"], string> = {
  queued: "У черзі",
  running: "Виконується",
  succeeded: "Успішно",
  failed: "Помилка",
};

export const syncStatusLabel = (status: SyncJob["status"]) => LABELS[status];

export const isJobActive = (job: SyncJob) => job.status === "queued" || job.status === "running";

export function useSyncJobs(page: number, pollMs = SYNC_POLL_MS) {
  return useQuery({
    queryKey: ["admin", "sync-jobs", page],
    queryFn: () =>
      request<SyncJobsResponse>("/admin/sync-jobs", {
        query: { limit: SYNC_PAGE_SIZE, offset: (page - 1) * SYNC_PAGE_SIZE },
      }),
    refetchInterval: (query) => (query.state.data?.sync_jobs.some(isJobActive) ? pollMs : false),
  });
}

export function useRunSync() {
  const queryClient = useQueryClient();
  return useMutation<SyncJob, ApiError, SyncSource>({
    mutationFn: (source) =>
      request<SyncJob>("/admin/sync-jobs", { method: "POST", body: { source } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "sync-jobs"] }),
  });
}
