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
