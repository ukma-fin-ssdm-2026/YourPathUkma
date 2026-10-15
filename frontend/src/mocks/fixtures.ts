// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: handlers.test.ts.
// Форми відповідей за docs/api/contract.md §3.1-§3.2.
import type {
  AcademicCategory,
  AcademicRecord,
  AcademicYear,
  AuthResponse,
  AuthUser,
  Credits,
  Me,
  ModerationItem,
  NormativeCourse,
  SyncJob,
} from "../api/types";

export const mockUser: AuthUser = {
  id: 42,
  email: "student@ukma.edu.ua",
  full_name: "Владислав Смирнов",
  role: "student",
};

/** Студент, який щойно зайшов: онбординг ще не пройдено. */
export function emptyMe(): Me {
  return {
    ...mockUser,
    student: {
      faculty: "ФІ",
      specialty: null,
      course_year: null,
      course_year_source: null,
      onboarding_required: true,
      can_create_plan: false,
      load_levels_mode: "manual",
      credits: {
        total_used: 0,
        total_limit: 240,
        free_choice_used: 0,
        free_choice_limit: 25,
        professional_used: 0,
        professional_limit: 54,
      },
      saz_synced_at: null,
    },
  };
}

export function authResponse(): AuthResponse {
  return { access_token: "mock-access-token", token_type: "Bearer", expires_in: 900, user: mockUser };
}

function history(
  academicYear: number,
  courseYear: number,
  parts: Record<AcademicCategory, number[]>,
): AcademicYear {
  let id = courseYear * 100;
  const records: AcademicRecord[] = (Object.keys(parts) as AcademicCategory[]).flatMap((category) =>
    parts[category].map((credits) => ({
      id: ++id,
      academic_year: academicYear,
      course_year: courseYear,
      course_id: null,
      title: `Дисципліна ${id}`,
      trimester: 1,
      credits,
      category,
      source: "self_declared",
      verified: false,
    })),
  );
  const total = records.reduce((sum, record) => sum + record.credits, 0);
  return { academic_year: academicYear, course_year: courseYear, total_credits: total, records };
}

/** Історія двох пройдених курсів: 60 + 58,5 кредитів. */
export function academicHistory(): AcademicYear[] {
  return [
    history(2023, 1, { normative: [6, 6, 6, 6, 6, 6, 6], professional: [6, 6], free_choice: [3, 3] }),
    history(2024, 2, { normative: [6, 6, 6, 6, 6, 6, 4.5], professional: [5, 5, 5], free_choice: [3] }),
  ];
}

/** Лічильники профілю, узгоджені з academicHistory(). */
export function historyCredits(): Credits {
  const records = academicHistory().flatMap((year) => year.records);
  const sum = (category: AcademicCategory) =>
    records.filter((record) => record.category === category).reduce((total, record) => total + record.credits, 0);
  return {
    total_used: sum("normative") + sum("professional") + sum("free_choice"),
    total_limit: 240,
    free_choice_used: sum("free_choice"),
    free_choice_limit: 25,
    professional_used: sum("professional"),
    professional_limit: 54,
  };
}

/** Нормативні, які «розпізнав» мок; остання не знайдена в каталозі (course_id: null). */
export function normativeCourses(): NormativeCourse[] {
  return [
    { course_id: 301, raw_title: "Архітектура ПЗ", trimester: 1, credits: 6 },
    { course_id: 302, raw_title: "Проєктний практикум", trimester: 2, credits: 9 },
    { course_id: 303, raw_title: "Виробнича практика", trimester: 3, credits: 12 },
    { course_id: null, raw_title: "Фізичне виховання", trimester: 2, credits: 2 },
  ];
}

/** Початковий журнал синхронізації для dev: одна невдала й одна успішна задача. */
export function seedSyncJobs(): SyncJob[] {
  const admin = { id: 1, full_name: "Адміністратор" };
  return [
    {
      id: 2,
      source: "saz_catalog",
      initiator: "admin",
      initiated_by: admin,
      status: "failed",
      started_at: "2026-10-08T09:00:00Z",
      finished_at: "2026-10-08T09:04:10Z",
      added_count: 0,
      updated_count: 0,
      error_message: "Не вдалося знайти таблицю дисциплін на сторінці САЗ",
    },
    {
      id: 1,
      source: "saz_catalog",
      initiator: "scheduler",
      initiated_by: null,
      status: "succeeded",
      started_at: "2026-10-01T03:00:00Z",
      finished_at: "2026-10-01T03:05:42Z",
      added_count: 4,
      updated_count: 11,
      error_message: null,
    },
  ];
}

/** Початкова черга модерації для dev: дві зміни, два додавання й одне видалення. */
export function seedModerationItems(): ModerationItem[] {
  const base = { sync_job_id: 2, status: "pending", reviewed_by: null, reviewed_at: null } as const;
  return [
    {
      ...base,
      id: 501,
      course_id: 101,
      change_type: "update",
      payload: { title: "Функціональне програмування", credits: 4, trimester: 1 },
      diff: { credits: { old: 5, new: 4 } },
    },
    {
      ...base,
      id: 502,
      course_id: 102,
      change_type: "update",
      payload: { title: "Бази даних", credits: 5, trimester: 2 },
      diff: { trimester: { old: 1, new: 2 }, title: { old: "Реляційні БД", new: "Бази даних" } },
    },
    {
      ...base,
      id: 503,
      course_id: null,
      change_type: "add",
      payload: { title: "Машинне навчання", credits: 4, trimester: 2 },
      diff: null,
    },
    {
      ...base,
      id: 504,
      course_id: null,
      change_type: "add",
      payload: { title: "Хмарні обчислення", credits: 3, trimester: 3 },
      diff: null,
    },
    {
      ...base,
      id: 505,
      course_id: 110,
      change_type: "remove",
      payload: { title: "Основи Pascal" },
      diff: null,
    },
  ];
}
