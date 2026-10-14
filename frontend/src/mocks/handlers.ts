// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: handlers.test.ts.
// Обробники лише для 🟡-ендпоінтів (яких ще немає в бекенді). Ендпоінт входу названо
// POST /auth/microsoft як припущення (див. спеку, «Рішення автора», п.1).
import { http, HttpResponse } from "msw";
import type { ErrorDetail } from "../api/errors";
import type { DeaneryDocument } from "../api/types";
import { db } from "./db";
import { academicHistory, authResponse, historyCredits, normativeCourses } from "./fixtures";

const API = "*/api/v1";

function apiError(
  status: number,
  code: string,
  message: string,
  details: ErrorDetail[] = [],
  headers?: Record<string, string>,
) {
  return HttpResponse.json({ code, message, details }, { status, headers });
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

const hasAuth = (request: Request) => Boolean(request.headers.get("Authorization"));

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

export const handlers = [
  ...documentHandlers,
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
