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
