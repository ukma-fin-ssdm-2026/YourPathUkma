// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: тести розділів адмінки.
// Обробники `/admin/*` (🟡) зі станом у `db.admin`.
import { http, HttpResponse } from "msw";
import type { SyncJob } from "../api/types";
import { db } from "./db";
import { API, apiError, hasAuth, paginate, unauthorized } from "./http";

const isActive = (job: SyncJob) => job.status === "queued" || job.status === "running";

/** Кожен запит списку просуває активні задачі: queued (1-й запит) → running → succeeded. */
function advanceSyncJobs(): void {
  for (const job of db.admin.syncJobs.filter(isActive)) {
    const polls = (db.admin.syncPolls[job.id] = (db.admin.syncPolls[job.id] ?? 0) + 1);
    if (polls === 2) job.status = "running";
    if (polls >= 3) {
      job.status = "succeeded";
      job.finished_at = new Date().toISOString();
      job.added_count = 3;
      job.updated_count = 7;
    }
  }
}

const syncHandlers = [
  http.get(`${API}/admin/sync-jobs`, ({ request }) => {
    if (!hasAuth(request)) return unauthorized();
    advanceSyncJobs();
    const sorted = [...db.admin.syncJobs].sort((a, b) => b.id - a.id);
    const { page, pagination } = paginate(sorted, new URL(request.url));
    return HttpResponse.json({ sync_jobs: page, pagination });
  }),

  http.post(`${API}/admin/sync-jobs`, async ({ request }) => {
    if (!hasAuth(request)) return unauthorized();
    const { source } = (await request.json()) as { source: SyncJob["source"] };
    if (db.admin.syncJobs.some((job) => job.source === source && isActive(job))) {
      return apiError(409, "SYNC_JOB_ALREADY_RUNNING", "Для цього джерела вже йде синхронізація");
    }
    const job: SyncJob = {
      id: Math.max(0, ...db.admin.syncJobs.map((j) => j.id)) + 1,
      source,
      initiator: "admin",
      initiated_by: { id: 1, full_name: "Адміністратор" },
      status: "queued",
      started_at: new Date().toISOString(),
      finished_at: null,
      added_count: 0,
      updated_count: 0,
      error_message: null,
    };
    db.admin.syncJobs.push(job);
    return HttpResponse.json(job, {
      status: 202,
      headers: { Location: `/api/v1/admin/sync-jobs/${job.id}` },
    });
  }),
];

export const adminHandlers = [...syncHandlers];
