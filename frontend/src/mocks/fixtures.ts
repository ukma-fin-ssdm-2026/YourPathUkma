// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: handlers.test.ts.
// Форми відповідей за docs/api/contract.md §3.1-§3.2.
import type { AuthResponse, AuthUser, Me } from "../api/types";

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
