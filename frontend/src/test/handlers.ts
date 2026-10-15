// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: тести, що його використовують.
// Тестові відповіді ✅-ендпоінтів (які в dev ходять на реальний бекенд) для `server.use(...)`.
import { http, HttpResponse } from "msw";
import type { ConfigResponse } from "../api/types";

export function configFixture(): ConfigResponse {
  return {
    api_version: "1.0.0",
    allowed_email_domain: "ukma.edu.ua",
    reviews_url: "https://example.ukma.edu.ua/reviews",
    limits: {
      total_credits: 240,
      free_choice_credits: 25,
      professional_credits: 54,
      min_year_credits: 57,
      max_directions: 3,
      max_plan_items: 30,
      max_item_credits: 30,
      academic_year_min: 2024,
      academic_year_max: 2030,
      max_upload_bytes: 10485760,
    },
    load_levels: {
      low: { max_hours_per_week: 20 },
      medium: { min_hours_per_week: 20, max_hours_per_week: 23 },
      high: { min_hours_per_week: 23, max_hours_per_week: 25 },
    },
    features: { ai_generation: false, certificate_programs: false, saz_sync: false, plan_export: true },
  };
}

export const configHandler = (overrides: Partial<ConfigResponse> = {}) =>
  http.get("*/api/v1/config", () => HttpResponse.json({ ...configFixture(), ...overrides }));

import type { Direction, Discipline } from "../api/types";

export function disciplineFixture(overrides: Partial<Discipline> = {}): Discipline {
  return {
    id: 101,
    title: "Функціональне програмування",
    description: "Основи функціональної парадигми.",
    discipline_type: "elective",
    instructor: "Петренко І. М.",
    recommended_year: 2,
    trimester: 1,
    credits: 5,
    directions: ["Software Engineering"],
    ...overrides,
  };
}

/** GET /disciplines: віддає items як є; `onRequest` бачить адресу запиту (для перевірки параметрів). */
export function disciplinesHandler(
  items: Discipline[],
  options: { total?: number; onRequest?: (url: URL) => void } = {},
) {
  return http.get("*/api/v1/disciplines", ({ request }) => {
    const url = new URL(request.url);
    options.onRequest?.(url);
    const limit = Number(url.searchParams.get("limit") ?? 20);
    const offset = Number(url.searchParams.get("offset") ?? 0);
    const total = options.total ?? items.length;
    return HttpResponse.json({
      disciplines: items,
      pagination: { limit, offset, total, has_more: offset + limit < total },
    });
  });
}

export function directionsHandler(names: string[]) {
  const directions: Direction[] = names.map((name, index) => ({ id: index + 1, name, description: null }));
  return http.get("*/api/v1/directions", () => HttpResponse.json({ directions }));
}

import type { PlanResponse } from "../api/types";

export function planFixture(overrides: Partial<PlanResponse> = {}): PlanResponse {
  return {
    id: 1,
    student_id: 42,
    academic_year: 2026,
    course: 3,
    load_levels: { autumn: "medium", spring: "high", summer: "low" },
    items: [],
    status: "draft",
    total_credits: 58,
    free_elective_credits: 3,
    created_at: "2026-10-08T10:00:00Z",
    ...overrides,
  };
}

/** GET /plans: віддає plans як є; `onRequest` бачить адресу запиту. */
export function plansHandler(plans: PlanResponse[], onRequest?: (url: URL) => void) {
  return http.get("*/api/v1/plans", ({ request }) => {
    const url = new URL(request.url);
    onRequest?.(url);
    return HttpResponse.json({
      plans,
      pagination: { limit: 100, offset: 0, total: plans.length, has_more: false },
    });
  });
}

import type { Instructor } from "../api/types";

/** GET /instructors: віддає items як є; `onRequest` бачить адресу запиту. */
export function instructorsHandler(items: Instructor[], onRequest?: (url: URL) => void) {
  return http.get("*/api/v1/instructors", ({ request }) => {
    const url = new URL(request.url);
    onRequest?.(url);
    const limit = Number(url.searchParams.get("limit") ?? 20);
    return HttpResponse.json({
      instructors: items,
      pagination: { limit, offset: 0, total: items.length, has_more: false },
    });
  });
}

import { delay, type RequestHandler } from "msw";
import type { PlanItem } from "../api/types";

interface PlanBody {
  academic_year: number;
  course: number;
  load_levels: PlanResponse["load_levels"];
  items: PlanItem[];
}

/** POST /plans/validate: ті самі правила, що в бекенді. `delayMs` дозволяє змоделювати повільну відповідь. */
export function validateHandler(
  onRequest?: (body: PlanBody) => void,
  delayMs?: (body: PlanBody) => number,
) {
  return http.post("*/api/v1/plans/validate", async ({ request }) => {
    const body = (await request.json()) as PlanBody;
    onRequest?.(body);
    if (delayMs) await delay(delayMs(body));
    const items = body.items;
    const free = items.filter((i) => i.is_free_elective).reduce((s, i) => s + i.credits, 0);
    const total = items.reduce((s, i) => s + i.credits, 0);
    const errors: { code: string; message: string; field: string | null }[] = [];
    const ids = items.map((i) => i.course_id);
    if (new Set(ids).size !== ids.length) {
      errors.push({ code: "DUPLICATE_COURSE", message: "Дисципліни в плані не повинні повторюватись", field: null });
    }
    if (items.length > 0 && items.every((i) => i.is_free_elective)) {
      errors.push({ code: "ONLY_FREE_ELECTIVES", message: "Не можна обрати лише вільний вибір", field: null });
    }
    if (free > 25) {
      errors.push({ code: "FREE_ELECTIVE_LIMIT_EXCEEDED", message: `Перевищено ліміт: ${free} > 25`, field: null });
    }
    const warnings = Object.values(body.load_levels).includes("low")
      ? [{ code: "LOW_LOAD_FUTURE_INCREASE", message: "Низьке навантаження", field: null }]
      : [];
    const byTrimester: Record<string, number> = { "1": 0, "2": 0, "3": 0 };
    for (const item of items) byTrimester[String(item.trimester)]! += item.credits;
    return HttpResponse.json({
      valid: errors.length === 0,
      errors,
      warnings,
      summary: {
        total_credits: total,
        free_elective_credits: free,
        free_elective_used_all_years: free,
        free_elective_remaining: 25 - free,
        year_total_credits: total,
        credits_by_trimester: byTrimester,
      },
    });
  });
}

/** POST /plans, GET і PUT /plans/{id} зі станом у пам'яті; `calls` рахує звернення. */
export function plansCrudHandlers(initial: PlanResponse[] = []): {
  handlers: RequestHandler[];
  calls: { post: number; put: number; get: number };
  bodies: PlanBody[];
} {
  const plans = new Map(initial.map((plan) => [plan.id, plan]));
  const calls = { post: 0, put: 0, get: 0 };
  const bodies: PlanBody[] = [];
  let nextId = Math.max(0, ...initial.map((plan) => plan.id)) + 1;
  const fromBody = (id: number, body: PlanBody, status: PlanResponse["status"]): PlanResponse =>
    planFixture({
      id,
      academic_year: body.academic_year,
      course: body.course,
      load_levels: body.load_levels,
      items: body.items,
      status,
      total_credits: body.items.reduce((s, i) => s + i.credits, 0),
      free_elective_credits: body.items.filter((i) => i.is_free_elective).reduce((s, i) => s + i.credits, 0),
    });
  const notFound = () =>
    HttpResponse.json({ code: "PLAN_NOT_FOUND", message: "План не знайдено", details: [] }, { status: 404 });
  const handlers = [
    http.post("*/api/v1/plans", async ({ request }) => {
      calls.post += 1;
      const body = (await request.json()) as PlanBody;
      bodies.push(body);
      const plan = fromBody(nextId++, body, "draft");
      plans.set(plan.id, plan);
      return HttpResponse.json(plan, { status: 201 });
    }),
    http.get("*/api/v1/plans/:id", ({ params }) => {
      calls.get += 1;
      const plan = plans.get(Number(params.id));
      return plan ? HttpResponse.json(plan) : notFound();
    }),
    http.put("*/api/v1/plans/:id", async ({ params, request }) => {
      calls.put += 1;
      const existing = plans.get(Number(params.id));
      if (!existing) return notFound();
      if (existing.status !== "draft") {
        return HttpResponse.json(
          { code: "PLAN_NOT_EDITABLE", message: "Редагувати можна лише чернетку", details: [] },
          { status: 409 },
        );
      }
      const body = (await request.json()) as PlanBody;
      bodies.push(body);
      const plan = fromBody(existing.id, body, "draft");
      plans.set(plan.id, plan);
      return HttpResponse.json(plan);
    }),
  ];
  return { handlers, calls, bodies };
}

import type { SyncJob } from "../api/types";

export function syncJobFixture(overrides: Partial<SyncJob> = {}): SyncJob {
  return {
    id: 1,
    source: "saz_catalog",
    initiator: "admin",
    initiated_by: { id: 1, full_name: "Адміністратор" },
    status: "succeeded",
    started_at: "2026-10-08T09:00:00Z",
    finished_at: "2026-10-08T09:04:10Z",
    added_count: 0,
    updated_count: 0,
    error_message: null,
    ...overrides,
  };
}

import type { ModerationItem } from "../api/types";

export function moderationItemFixture(overrides: Partial<ModerationItem> = {}): ModerationItem {
  return {
    id: 501,
    sync_job_id: 31,
    course_id: 101,
    change_type: "update",
    payload: { title: "Функціональне програмування", credits: 4, trimester: 1 },
    diff: { credits: { old: 5, new: 4 } },
    status: "pending",
    reviewed_by: null,
    reviewed_at: null,
    ...overrides,
  };
}

import type { AdminUser, AuditLogEntry } from "../api/types";

export function auditEntryFixture(overrides: Partial<AuditLogEntry> = {}): AuditLogEntry {
  return {
    id: 9001,
    actor: { id: 42, full_name: "Владислав Смирнов" },
    action: "plan.read",
    object_type: "IndividualPlan",
    object_id: 3,
    outcome: "denied",
    ip: "10.0.0.15",
    created_at: "2026-10-08T10:00:00Z",
    ...overrides,
  };
}

export function adminUserFixture(overrides: Partial<AdminUser> = {}): AdminUser {
  return {
    id: 42,
    email: "vl.smyrnov@ukma.edu.ua",
    full_name: "Владислав Смирнов",
    role: "student",
    created_at: "2026-09-01T08:00:00Z",
    last_login_at: "2026-10-08T09:55:00Z",
    student: {
      specialty: "Інженерія програмного забезпечення",
      course_year: 3,
      course_year_source: "self_declared",
    },
    ...overrides,
  };
}
