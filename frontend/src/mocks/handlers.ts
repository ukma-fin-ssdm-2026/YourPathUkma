// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: handlers.test.ts.
// `handlers` — лише те, чого бекенд ще не має (вхід, адмінка); завжди увімкнено при VITE_USE_MOCKS.
// `backendHandlers` — копії вже реалізованих ендпоінтів для тестів і режиму `full`.
// Ендпоінт входу названо POST /auth/microsoft як припущення (у бекенді поки лише /auth/google).
import { http, HttpResponse } from "msw";
import type { ErrorDetail } from "../api/errors";
import type { DeaneryDocument, Preferences } from "../api/types";
import { adminHandlers } from "./admin";
import { db } from "./db";
import { API, apiError, hasAuth, unauthorized } from "./http";
import { academicHistory, authResponse, historyCredits, normativeCourses } from "./fixtures";

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

/** Документ «розпізнається» після другого запиту; "scan" у назві дає помилку розпізнавання. */
function resolveDocument(doc: DeaneryDocument): DeaneryDocument {
  const polls = (db.docPolls[doc.id] = (db.docPolls[doc.id] ?? 0) + 1);
  if (doc.parse_status === "pending" && polls >= 2) {
    if (doc.original_filename.includes("scan")) {
      doc.parse_status = "failed";
      doc.parse_error = "Не вдалося прочитати таблицю дисциплін";
    } else {
      doc.parse_status = "parsed";
      doc.normative_courses = normativeCourses();
    }
  }
  return doc;
}

const documentHandlers = [
  http.post(`${API}/deanery-documents`, async ({ request }) => {
    if (!hasAuth(request)) return unauthorized();
    // У тестах (jsdom) request.formData() недоступний, тож читаємо multipart як текст.
    const body = await request.text();
    const filename = /filename="([^"]+)"/.exec(body)?.[1] ?? "document.pdf";
    const year = Number(/name="academic_year"\r\n\r\n(\d+)/.exec(body)?.[1] ?? 0);
    if (filename.includes("huge")) {
      return apiError(413, "FILE_TOO_LARGE", "Файл завеликий: максимум 10 МБ");
    }
    if (!/\.(pdf|docx)$/i.test(filename)) {
      return apiError(415, "UNSUPPORTED_FILE_TYPE", "Підтримуються лише PDF і DOCX");
    }
    const doc: DeaneryDocument = {
      id: db.nextDocId++,
      academic_year: year,
      original_filename: filename,
      mime_type: /\.docx$/i.test(filename) ? "docx" : "pdf",
      size_bytes: body.length,
      parse_status: "pending",
      parse_error: null,
      uploaded_at: new Date().toISOString(),
      normative_courses: [],
    };
    db.documents.push(doc);
    return HttpResponse.json(doc, {
      status: 202,
      headers: { Location: `/api/v1/deanery-documents/${doc.id}` },
    });
  }),

  http.get(`${API}/deanery-documents`, ({ request }) => {
    if (!hasAuth(request)) return unauthorized();
    const year = new URL(request.url).searchParams.get("academic_year");
    const documents = db.documents.filter((doc) => !year || doc.academic_year === Number(year));
    return HttpResponse.json({ deanery_documents: documents });
  }),

  http.get(`${API}/deanery-documents/:id`, ({ request, params }) => {
    if (!hasAuth(request)) return unauthorized();
    const doc = db.documents.find((d) => String(d.id) === params.id);
    if (!doc) return apiError(404, "DOCUMENT_NOT_FOUND", "Документ не знайдено");
    return HttpResponse.json(resolveDocument(doc));
  }),

  http.delete(`${API}/deanery-documents/:id`, ({ request, params }) => {
    if (!hasAuth(request)) return unauthorized();
    const doc = db.documents.find((d) => String(d.id) === params.id);
    if (!doc) return apiError(404, "DOCUMENT_NOT_FOUND", "Документ не знайдено");
    if (doc.original_filename.includes("inuse")) {
      return apiError(409, "DOCUMENT_IN_USE", "Документ використовується в плані, який уже подано");
    }
    db.documents = db.documents.filter((d) => d.id !== doc.id);
    return new HttpResponse(null, { status: 204 });
  }),
];

const preferencesHandlers = [
  http.get(`${API}/preferences/:year`, ({ request, params }) => {
    if (!hasAuth(request)) return unauthorized();
    const saved = db.preferences[Number(params.year)];
    return saved
      ? HttpResponse.json(saved)
      : apiError(404, "PREFERENCES_NOT_FOUND", "Побажань на цей рік ще не збережено");
  }),

  http.put(`${API}/preferences/:year`, async ({ request, params }) => {
    if (!hasAuth(request)) return unauthorized();
    const body = (await request.json()) as Preferences;
    const details: ErrorDetail[] = [];
    if (body.direction_ids.length > 3) {
      details.push({ field: "direction_ids", message: "Не більше 3 напрямків" });
    }
    if (body.preferred_instructor_ids.some((id) => body.unwanted_instructor_ids.includes(id))) {
      details.push({
        field: "preferred_instructor_ids",
        message: "Викладач не може бути і бажаним, і небажаним",
      });
    }
    if (details.length > 0) return apiError(422, "VALIDATION_ERROR", "Невалідні вхідні дані", details);
    const saved: Preferences = {
      ...body,
      academic_year: Number(params.year),
      updated_at: new Date().toISOString(),
    };
    db.preferences[saved.academic_year] = saved;
    return HttpResponse.json(saved);
  }),
];

const planHandlers = [
  // GET /plans/{id}/export ще не реалізовано в бекенді (🟡): віддаємо короткий PDF-заглушку.
  http.get(`${API}/plans/:id/export`, ({ request }) => {
    if (!hasAuth(request)) return unauthorized();
    return new HttpResponse("%PDF-1.4\n% mock plan\n", {
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": 'attachment; filename="plan-2026.pdf"',
      },
    });
  }),

  // POST /plans/{id}/submit ще не реалізовано в бекенді (🟡): повертаємо заглушку з новим статусом.
  http.post(`${API}/plans/:id/submit`, ({ request, params }) => {
    if (!hasAuth(request)) return unauthorized();
    return HttpResponse.json({
      id: Number(params.id),
      student_id: 42,
      academic_year: new Date().getFullYear(),
      course: 3,
      load_levels: { autumn: "medium", spring: "medium", summer: "medium" },
      items: [],
      status: "submitted",
      total_credits: 0,
      free_elective_credits: 0,
      created_at: new Date().toISOString(),
    });
  }),
];

/** Завжди увімкнені моки: вхід (бекенд має лише заглушку Google) та адмінка. */
export const handlers = [
  ...adminHandlers,
  http.post(`${API}/auth/microsoft`, async ({ request }) => {
    const body = (await request.json().catch(() => null)) as { code?: string } | null;
    // Спеціальний код для перевірки помилки домену (FR-012).
    if (body?.code === "blocked") {
      return apiError(403, "DOMAIN_NOT_ALLOWED", "Пошта не з домену ukma.edu.ua", [], {
        "X-Request-ID": "a41f-9c2e",
      });
    }
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

];

const meHandlers = [
  http.get(`${API}/me`, ({ request }) =>
    request.headers.get("Authorization") ? HttpResponse.json(db.me) : unauthorized(),
  ),

  http.get(`${API}/me/academic-history`, ({ request }) =>
    request.headers.get("Authorization")
      ? HttpResponse.json({ years: academicHistory() })
      : unauthorized(),
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
        credits: historyCredits(),
      },
    };
    return HttpResponse.json(db.me);
  }),
];

/** Копія ендпоінтів, які бекенд уже реалізував. Лише для тестів і режиму `full`. */
export const backendHandlers = [
  ...planHandlers,
  ...preferencesHandlers,
  ...documentHandlers,
  ...meHandlers,
];
