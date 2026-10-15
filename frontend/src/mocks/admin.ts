// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: тести розділів адмінки.
// Обробники `/admin/*` (🟡) зі станом у `db.admin`.
import { http, HttpResponse } from "msw";
import type { BulkReviewResult, ModerationItem, SyncJob } from "../api/types";
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

function review(item: ModerationItem, decision: "approve" | "reject"): void {
  item.status = decision === "approve" ? "approved" : "rejected";
  item.reviewed_by = { id: 1, full_name: "Адміністратор" };
  item.reviewed_at = new Date().toISOString();
}

const moderationHandlers = [
  http.get(`${API}/admin/moderation-items`, ({ request }) => {
    if (!hasAuth(request)) return unauthorized();
    const url = new URL(request.url);
    const status = url.searchParams.get("status") ?? "pending";
    const type = url.searchParams.get("change_type");
    const items = db.admin.moderationItems.filter(
      (item) => item.status === status && (!type || item.change_type === type),
    );
    const { page, pagination } = paginate(items, url);
    return HttpResponse.json({ moderation_items: page, pagination });
  }),

  http.post(`${API}/admin/moderation-items/bulk-review`, async ({ request }) => {
    if (!hasAuth(request)) return unauthorized();
    const { item_ids, decision } = (await request.json()) as {
      item_ids: number[];
      decision: "approve" | "reject";
    };
    if (item_ids.length < 1 || item_ids.length > 100) {
      return apiError(422, "VALIDATION_ERROR", "Невалідні вхідні дані", [
        { field: "item_ids", message: "Потрібно від 1 до 100 записів" },
      ]);
    }
    const result: BulkReviewResult = { approved: [], rejected: [], skipped: [] };
    for (const id of item_ids) {
      const item = db.admin.moderationItems.find((i) => i.id === id);
      if (!item || item.status !== "pending") {
        result.skipped.push({
          id,
          code: item ? "MODERATION_ITEM_ALREADY_REVIEWED" : "MODERATION_ITEM_NOT_FOUND",
        });
        continue;
      }
      review(item, decision);
      (decision === "approve" ? result.approved : result.rejected).push(id);
    }
    return HttpResponse.json(result);
  }),

  http.post(`${API}/admin/moderation-items/:id/:decision`, ({ request, params }) => {
    if (!hasAuth(request)) return unauthorized();
    const item = db.admin.moderationItems.find((i) => String(i.id) === params.id);
    if (!item) return apiError(404, "MODERATION_ITEM_NOT_FOUND", "Запис не знайдено");
    if (item.status !== "pending") {
      return apiError(409, "MODERATION_ITEM_ALREADY_REVIEWED", "Запис уже розглянуто");
    }
    review(item, params.decision === "approve" ? "approve" : "reject");
    return HttpResponse.json(item);
  }),
];

export const adminHandlers = [...syncHandlers, ...moderationHandlers];
