// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: handlers.test.ts.
// Обробники лише для 🟡-ендпоінтів (яких ще немає в бекенді). Ендпоінт входу названо
// POST /auth/microsoft як припущення (див. спеку, «Рішення автора», п.1).
import { http, HttpResponse } from "msw";
import type { ErrorDetail } from "../api/errors";
import { db } from "./db";
import { authResponse } from "./fixtures";

const API = "*/api/v1";

function apiError(status: number, code: string, message: string, details: ErrorDetail[] = []) {
  return HttpResponse.json({ code, message, details }, { status });
}

const unauthorized = () =>
  apiError(401, "UNAUTHORIZED", "Відсутній або некоректний токен авторизації");

function validateOnboarding(body: unknown): ErrorDetail[] {
  const { course_year, specialty } = (body ?? {}) as { course_year?: unknown; specialty?: unknown };
  const details: ErrorDetail[] = [];
  if (!Number.isInteger(course_year) || (course_year as number) < 1 || (course_year as number) > 4) {
    details.push({ field: "course_year", message: "Input should be between 1 and 4" });
  }
  const length = typeof specialty === "string" ? specialty.trim().length : 0;
  if (length < 2 || length > 150) {
    details.push({ field: "specialty", message: "String should have from 2 to 150 characters" });
  }
  return details;
}

export const handlers = [
  http.post(`${API}/auth/microsoft`, () => {
    db.signedIn = true;
    return HttpResponse.json(authResponse());
  }),

  http.post(`${API}/auth/refresh`, () =>
    db.signedIn ? HttpResponse.json(authResponse()) : unauthorized(),
  ),

  http.post(`${API}/auth/logout`, () => {
    db.signedIn = false;
    return new HttpResponse(null, { status: 204 });
  }),

  http.get(`${API}/me`, ({ request }) =>
    request.headers.get("Authorization") ? HttpResponse.json(db.me) : unauthorized(),
  ),

  http.post(`${API}/me/onboarding`, async ({ request }) => {
    if (!request.headers.get("Authorization")) return unauthorized();
    const student = db.me.student;
    if (!student) return apiError(404, "USER_NOT_FOUND", "Профіль студента не знайдено");
    if (!student.onboarding_required) {
      return apiError(409, "ALREADY_ONBOARDED", "Онбординг уже пройдено, змінити може лише адміністратор");
    }
    const body: unknown = await request.json().catch(() => null);
    const details = validateOnboarding(body);
    if (details.length > 0) {
      return apiError(422, "VALIDATION_ERROR", "Невалідні вхідні дані", details);
    }
    const { course_year, specialty } = body as { course_year: 1 | 2 | 3 | 4; specialty: string };
    db.me = {
      ...db.me,
      student: {
        ...student,
        specialty: specialty.trim(),
        course_year,
        course_year_source: "self_declared",
        onboarding_required: false,
        can_create_plan: course_year >= 2,
        load_levels_mode: course_year === 4 ? "auto" : "manual",
      },
    };
    return HttpResponse.json(db.me);
  }),
];
