// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: handlers.test.ts.
// Форми відповідей за docs/api/contract.md §3.1-§3.2.
import type {
  AcademicCategory,
  AdminUser,
  AuditLogEntry,
  Direction,
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
  role: import.meta.env.VITE_MOCK_ROLE === "admin" ? "admin" : "student",
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

/** Ідентифікатор адміністратора, від імені якого працюють адмін-моки (для CANNOT_CHANGE_OWN_ROLE). */
export const MOCK_ADMIN_ID = 1;

/** Початкові користувачі для dev: адміністратор і троє студентів. */
export function seedAdminUsers(): AdminUser[] {
  const student = (
    id: number,
    full_name: string,
    email: string,
    course_year: 1 | 2 | 3 | 4 | null,
    source: "self_declared" | "admin" | "saz_sync" | null,
  ): AdminUser => ({
    id,
    email,
    full_name,
    role: "student",
    created_at: "2026-09-01T08:00:00Z",
    last_login_at: "2026-10-08T09:55:00Z",
    student: {
      specialty: "Інженерія програмного забезпечення",
      course_year,
      course_year_source: source,
    },
  });
  return [
    {
      id: MOCK_ADMIN_ID,
      email: "admin@ukma.edu.ua",
      full_name: "Адміністратор",
      role: "admin",
      created_at: "2026-08-20T08:00:00Z",
      last_login_at: "2026-10-09T07:30:00Z",
      student: null,
    },
    student(42, "Владислав Смирнов", "vl.smyrnov@ukma.edu.ua", 3, "self_declared"),
    student(43, "Олена Коваль", "o.koval@ukma.edu.ua", 2, "saz_sync"),
    student(44, "Андрій Мельник", "a.melnyk@ukma.edu.ua", null, null),
  ];
}

/** Напрямки, на які посилаються дисципліни/побажання: їх видалення дає 409 DIRECTION_IN_USE. */
export const DIRECTION_IDS_IN_USE = [3];

export function seedDirections(): Direction[] {
  return [
    { id: 1, name: "Data Science", description: "Дані та ML" },
    { id: 2, name: "Веброзробка", description: null },
    { id: 3, name: "Кібербезпека", description: "Захист систем" },
  ];
}

/** Журнал дій для dev; `old_value`/`new_value` віддає лише GET /admin/audit-log/{id}. */
export function seedAuditLog(): AuditLogEntry[] {
  const student = { id: 42, full_name: "Владислав Смирнов" };
  const admin = { id: MOCK_ADMIN_ID, full_name: "Адміністратор" };
  const entry = (
    id: number,
    actor: AuditLogEntry["actor"],
    action: string,
    object_type: string,
    object_id: number,
    outcome: AuditLogEntry["outcome"],
    extra: Partial<AuditLogEntry> = {},
  ): AuditLogEntry => ({
    id,
    actor,
    action,
    object_type,
    object_id,
    outcome,
    ip: "10.0.0.15",
    created_at: `2026-10-08T10:0${id - 9000}:00Z`,
    ...extra,
  });
  return [
    entry(9001, student, "plan.read", "IndividualPlan", 3, "denied"),
    entry(9002, admin, "auth.login", "User", MOCK_ADMIN_ID, "allowed"),
    entry(9003, admin, "user.update", "User", 42, "allowed", {
      old_value: { role: "student" },
      new_value: { role: "admin" },
    }),
    entry(9004, admin, "plan.update", "IndividualPlan", 3, "allowed", {
      new_value: { note: "<img src=x onerror=alert(1)>" },
    }),
    entry(9005, admin, "moderation.approve", "ModerationItem", 501, "allowed"),
    entry(9006, admin, "discipline.directions.update", "Discipline", 101, "allowed"),
  ];
}
