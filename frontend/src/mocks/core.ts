// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: core.test.ts і ручний запуск dev з VITE_USE_MOCKS=full.
// Обробники ✅-ендпоінтів, які реальний бекенд уже має. Вмикаються лише в режимі VITE_USE_MOCKS=full,
// щоб увесь застосунок можна було пройти без запущеного бекенду.
import { http, HttpResponse } from "msw";
import type { Discipline, Instructor, PlanItem, PlanResponse } from "../api/types";
import { db } from "./db";
import { API, apiError, hasAuth, paginate, unauthorized } from "./http";

const DIRECTIONS = [
  "Software Engineering",
  "Data Science",
  "Кібербезпека",
  "Інтелектуальні системи",
];

const INSTRUCTORS: Instructor[] = [
  { id: 1, full_name: "Петренко І. М." },
  { id: 2, full_name: "Коваленко О. В." },
  { id: 3, full_name: "Мельник Т. С." },
  { id: 4, full_name: "Шевченко-Литвиненко Олександра Борисівна" },
];

function discipline(
  id: number,
  title: string,
  instructor: number,
  year: 2 | 3 | 4,
  trimester: 1 | 2 | 3,
  credits: number,
  directions: string[],
): Discipline {
  return {
    id,
    title,
    description: `Курс «${title}»: лекції, практичні заняття й індивідуальний проєкт.`,
    discipline_type: "elective",
    instructor: INSTRUCTORS[instructor - 1]!.full_name,
    recommended_year: year,
    trimester,
    credits,
    directions,
  };
}

const DISCIPLINES: Discipline[] = [
  discipline(101, "Функціональне програмування", 1, 2, 1, 5, [DIRECTIONS[0]!]),
  discipline(102, "Машинне навчання", 2, 3, 2, 6, [DIRECTIONS[1]!, DIRECTIONS[3]!]),
  discipline(103, "Основи кібербезпеки", 3, 2, 3, 4, [DIRECTIONS[2]!]),
  discipline(104, "Хмарні обчислення та розподілені системи з високим навантаженням", 4, 4, 1, 5, [
    DIRECTIONS[0]!,
  ]),
  discipline(105, "Аналіз даних на Python", 2, 2, 2, 5, [DIRECTIONS[1]!]),
  discipline(106, "Криптографія", 3, 3, 1, 4, [DIRECTIONS[2]!]),
  discipline(107, "Нейронні мережі", 1, 4, 2, 6, [DIRECTIONS[3]!, DIRECTIONS[1]!]),
  discipline(108, "Тестування програмного забезпечення", 1, 2, 3, 3, [DIRECTIONS[0]!]),
  discipline(109, "Візуалізація даних", 2, 3, 3, 3, [DIRECTIONS[1]!]),
  discipline(110, "Безпека веб-застосунків", 3, 3, 2, 5, [DIRECTIONS[2]!, DIRECTIONS[0]!]),
  discipline(111, "Обробка природної мови", 4, 4, 3, 5, [DIRECTIONS[3]!]),
  discipline(112, "Архітектура програмного забезпечення", 1, 3, 1, 5, [DIRECTIONS[0]!]),
  discipline(113, "Бази даних для аналітики", 2, 2, 1, 4, [DIRECTIONS[1]!]),
  discipline(114, "Етичний хакінг", 3, 4, 2, 5, [DIRECTIONS[2]!]),
  discipline(115, "Рекомендаційні системи", 4, 4, 3, 4, [DIRECTIONS[3]!, DIRECTIONS[1]!]),
];

const item = (d: Discipline, free = false): PlanItem => ({
  course_id: d.id,
  title: d.title,
  trimester: d.trimester,
  credits: d.credits,
  is_free_elective: free,
});

function build(
  id: number,
  status: PlanResponse["status"],
  items: PlanItem[],
  year = 2026,
): PlanResponse {
  return {
    id,
    student_id: 42,
    academic_year: year,
    course: 3,
    load_levels: { autumn: "medium", spring: "high", summer: "low" },
    items,
    status,
    total_credits: items.reduce((sum, i) => sum + i.credits, 0),
    free_elective_credits: items
      .filter((i) => i.is_free_elective)
      .reduce((sum, i) => sum + i.credits, 0),
    created_at: "2026-10-08T10:00:00Z",
  };
}

const seedPlans = (): PlanResponse[] => [
  build(1, "draft", [item(DISCIPLINES[0]!), item(DISCIPLINES[1]!), item(DISCIPLINES[2]!, true)]),
  build(2, "approved", [item(DISCIPLINES[4]!), item(DISCIPLINES[8]!, true)], 2025),
];

const state = { plans: seedPlans(), nextId: 3 };

export function resetCoreMocks(): void {
  state.plans = seedPlans();
  state.nextId = 3;
}

interface PlanBody {
  academic_year: number;
  course: number;
  load_levels: PlanResponse["load_levels"];
  items: PlanItem[];
}

function validate(body: PlanBody) {
  const free = body.items.filter((i) => i.is_free_elective).reduce((sum, i) => sum + i.credits, 0);
  const total = body.items.reduce((sum, i) => sum + i.credits, 0);
  const errors: { code: string; message: string; field: string | null }[] = [];
  if (new Set(body.items.map((i) => i.course_id)).size !== body.items.length) {
    errors.push({
      code: "DUPLICATE_COURSE",
      message: "Дисципліни в плані не повинні повторюватись",
      field: null,
    });
  }
  if (body.items.length > 0 && body.items.every((i) => i.is_free_elective)) {
    errors.push({
      code: "ONLY_FREE_ELECTIVES",
      message: "Не можна обрати лише вільний вибір",
      field: null,
    });
  }
  if (free > 25) {
    errors.push({
      code: "FREE_ELECTIVE_LIMIT_EXCEEDED",
      message: `Перевищено ліміт вільного вибору: ${free} > 25`,
      field: null,
    });
  }
  const warnings = Object.values(body.load_levels).includes("low")
    ? [
        {
          code: "LOW_LOAD_FUTURE_INCREASE",
          message: "Низьке навантаження цього року збільшить його в наступних",
          field: null,
        },
      ]
    : [];
  const byTrimester: Record<string, number> = { "1": 0, "2": 0, "3": 0 };
  for (const i of body.items) byTrimester[String(i.trimester)]! += i.credits;
  return {
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
  };
}

const planNotFound = () => apiError(404, "PLAN_NOT_FOUND", "План не знайдено");
const find = (id: unknown) => state.plans.find((p) => p.id === Number(id));
const replace = (plan: PlanResponse) => {
  state.plans = state.plans.map((p) => (p.id === plan.id ? plan : p));
  return plan;
};

export const coreHandlers = [
  http.get(`${API}/config`, () =>
    HttpResponse.json({
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
      features: {
        ai_generation: false,
        certificate_programs: false,
        saz_sync: true,
        plan_export: true,
      },
    }),
  ),

  // Довідник напрямків спільний з адмінкою, тож додані там напрямки одразу видно скрізь.
  http.get(`${API}/directions`, () => HttpResponse.json({ directions: db.admin.directions })),

  http.get(`${API}/instructors`, ({ request }) => {
    const url = new URL(request.url);
    const q = (url.searchParams.get("q") ?? "").toLowerCase();
    const found = INSTRUCTORS.filter((i) => i.full_name.toLowerCase().includes(q));
    const { page, pagination } = paginate(found, url);
    return HttpResponse.json({ instructors: page, pagination });
  }),

  http.get(`${API}/disciplines`, ({ request }) => {
    if (!hasAuth(request)) return unauthorized();
    const url = new URL(request.url);
    const get = (key: string) => url.searchParams.get(key);
    const found = DISCIPLINES.filter(
      (d) =>
        (!get("direction") || d.directions?.includes(get("direction")!)) &&
        (!get("trimester") || d.trimester === Number(get("trimester"))) &&
        (!get("recommended_year") || d.recommended_year === Number(get("recommended_year"))) &&
        (!get("instructor") ||
          d.instructor.toLowerCase().includes(get("instructor")!.toLowerCase())) &&
        (!get("min_credits") || d.credits >= Number(get("min_credits"))) &&
        (!get("max_credits") || d.credits <= Number(get("max_credits"))),
    );
    const { page, pagination } = paginate(found, url, 20);
    return HttpResponse.json({ disciplines: page, pagination });
  }),

  http.get(`${API}/plans`, ({ request }) => {
    if (!hasAuth(request)) return unauthorized();
    const url = new URL(request.url);
    const status = url.searchParams.get("status");
    const { page, pagination } = paginate(
      state.plans.filter((p) => !status || p.status === status),
      url,
      100,
    );
    return HttpResponse.json({ plans: page, pagination });
  }),

  http.post(`${API}/plans/validate`, async ({ request }) =>
    HttpResponse.json(validate((await request.json()) as PlanBody)),
  ),

  http.post(`${API}/plans`, async ({ request }) => {
    const body = (await request.json()) as PlanBody;
    const plan = {
      ...build(state.nextId++, "draft", body.items, body.academic_year),
      course: body.course,
      load_levels: body.load_levels,
    };
    state.plans = [...state.plans, plan];
    return HttpResponse.json(plan, { status: 201 });
  }),

  http.get(`${API}/plans/:id`, ({ params }) => {
    const plan = find(params.id);
    return plan ? HttpResponse.json(plan) : planNotFound();
  }),

  http.put(`${API}/plans/:id`, async ({ params, request }) => {
    const existing = find(params.id);
    if (!existing) return planNotFound();
    if (existing.status !== "draft")
      return apiError(409, "PLAN_NOT_EDITABLE", "Редагувати можна лише чернетку");
    const body = (await request.json()) as PlanBody;
    return HttpResponse.json(
      replace({
        ...build(existing.id, "draft", body.items, body.academic_year),
        course: body.course,
        load_levels: body.load_levels,
      }),
    );
  }),

  http.delete(`${API}/plans/:id`, ({ params }) => {
    const existing = find(params.id);
    if (!existing) return planNotFound();
    if (existing.status !== "draft")
      return apiError(409, "PLAN_NOT_EDITABLE", "Видалити можна лише чернетку");
    state.plans = state.plans.filter((p) => p.id !== existing.id);
    return new HttpResponse(null, { status: 204 });
  }),

  http.post(`${API}/plans/:id/submit`, ({ params }) => {
    const existing = find(params.id);
    return existing
      ? HttpResponse.json(replace({ ...existing, status: "submitted" }))
      : planNotFound();
  }),
];
