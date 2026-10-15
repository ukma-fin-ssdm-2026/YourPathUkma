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
