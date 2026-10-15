// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: тести розділів адмінки.
// Обробники `/admin/*` (🟡) зі станом у `db.admin`.
import { http, HttpResponse } from "msw";
import type { ErrorDetail } from "../api/errors";
import type { AdminUserPatch, BulkReviewResult, ModerationItem, SyncJob } from "../api/types";
import { db } from "./db";
import { DIRECTION_IDS_IN_USE, MOCK_ADMIN_ID } from "./fixtures";
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

const userHandlers = [
  http.get(`${API}/admin/users`, ({ request }) => {
    if (!hasAuth(request)) return unauthorized();
    const url = new URL(request.url);
    const q = url.searchParams.get("q")?.toLowerCase();
    const role = url.searchParams.get("role");
    const users = db.admin.users.filter(
      (user) =>
        (!role || user.role === role) &&
        (!q || user.email.toLowerCase().includes(q) || user.full_name.toLowerCase().includes(q)),
    );
    const { page, pagination } = paginate(users, url);
    return HttpResponse.json({ users: page, pagination });
  }),

  http.patch(`${API}/admin/users/:id`, async ({ request, params }) => {
    if (!hasAuth(request)) return unauthorized();
    const user = db.admin.users.find((u) => String(u.id) === params.id);
    if (!user) return apiError(404, "USER_NOT_FOUND", "Користувача не знайдено");
    const patch = (await request.json()) as AdminUserPatch;
    if (patch.role && patch.role !== user.role && user.id === MOCK_ADMIN_ID) {
      return apiError(409, "CANNOT_CHANGE_OWN_ROLE", "Адмін не може змінити власну роль");
    }
    const details: ErrorDetail[] = [];
    const year = patch.student?.course_year;
    if (year !== undefined && !(Number.isInteger(year) && year >= 1 && year <= 4)) {
      details.push({ field: "student.course_year", message: "Input should be between 1 and 4" });
    }
    const specialty = patch.student?.specialty;
    if (specialty !== undefined && (specialty.length < 2 || specialty.length > 150)) {
      details.push({ field: "student.specialty", message: "String should have from 2 to 150 characters" });
    }
    if (details.length > 0) return apiError(422, "VALIDATION_ERROR", "Невалідні вхідні дані", details);
    if (patch.role) user.role = patch.role;
    if (patch.student && user.student) {
      Object.assign(user.student, patch.student, { course_year_source: "admin" });
    }
    return HttpResponse.json(user);
  }),
];

function validateDirection(body: { name?: string; description?: string | null }, id?: number) {
  const details: ErrorDetail[] = [];
  if (body.name !== undefined) {
    if (body.name.length < 2 || body.name.length > 50) {
      details.push({ field: "name", message: "String should have from 2 to 50 characters" });
    } else if (
      db.admin.directions.some((d) => d.id !== id && d.name.toLowerCase() === body.name!.toLowerCase())
    ) {
      return apiError(409, "DIRECTION_NAME_TAKEN", "Напрямок із такою назвою вже існує");
    }
  }
  return details.length > 0 ? apiError(422, "VALIDATION_ERROR", "Невалідні вхідні дані", details) : null;
}

const directionHandlers = [
  http.post(`${API}/admin/directions`, async ({ request }) => {
    if (!hasAuth(request)) return unauthorized();
    const body = (await request.json()) as { name: string; description?: string | null };
    const invalid = validateDirection(body);
    if (invalid) return invalid;
    const direction = {
      id: Math.max(0, ...db.admin.directions.map((d) => d.id)) + 1,
      name: body.name,
      description: body.description ?? null,
    };
    db.admin.directions.push(direction);
    return HttpResponse.json(direction, { status: 201 });
  }),

  http.patch(`${API}/admin/directions/:id`, async ({ request, params }) => {
    if (!hasAuth(request)) return unauthorized();
    const direction = db.admin.directions.find((d) => String(d.id) === params.id);
    if (!direction) return apiError(404, "DIRECTION_NOT_FOUND", "Напрямок не знайдено");
    const body = (await request.json()) as { name?: string; description?: string | null };
    const invalid = validateDirection(body, direction.id);
    if (invalid) return invalid;
    Object.assign(direction, body);
    return HttpResponse.json(direction);
  }),

  http.delete(`${API}/admin/directions/:id`, ({ request, params }) => {
    if (!hasAuth(request)) return unauthorized();
    const direction = db.admin.directions.find((d) => String(d.id) === params.id);
    if (!direction) return apiError(404, "DIRECTION_NOT_FOUND", "Напрямок не знайдено");
    if (DIRECTION_IDS_IN_USE.includes(direction.id)) {
      return apiError(409, "DIRECTION_IN_USE", "Напрямок прив'язаний до дисциплін або побажань");
    }
    db.admin.directions = db.admin.directions.filter((d) => d.id !== direction.id);
    return new HttpResponse(null, { status: 204 });
  }),
];

export const adminHandlers = [
  ...syncHandlers,
  ...moderationHandlers,
  ...userHandlers,
  ...directionHandlers,
];
