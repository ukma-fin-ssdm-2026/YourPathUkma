// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm run typecheck.
// Типи 🟡-ендпоінтів вручну за docs/api/contract.md (§3.0-§3.2). Типи ✅-ендпоінтів генеруються
// скриптом `npm run gen:api` у src/api/generated/ (у .gitignore).
export type { PlanStatus } from "../ui/Badge";

export type LoadLevel = "low" | "medium" | "high";
export type UserRole = "student" | "admin";

export interface Limits {
  total_credits: number;
  free_choice_credits: number;
  professional_credits: number;
  min_year_credits: number;
  max_directions: number;
  max_plan_items: number;
  max_item_credits: number;
  academic_year_min: number;
  academic_year_max: number;
  max_upload_bytes: number;
}

export interface LoadLevelHours {
  min_hours_per_week?: number | null;
  max_hours_per_week: number;
}

export interface Features {
  ai_generation: boolean;
  certificate_programs: boolean;
  saz_sync: boolean;
  plan_export: boolean;
}

export interface ConfigResponse {
  api_version: string;
  allowed_email_domain: string;
  reviews_url: string;
  limits: Limits;
  load_levels: Record<LoadLevel, LoadLevelHours>;
  features: Features;
}

export interface AuthUser {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

export interface Credits {
  total_used: number;
  total_limit: number;
  free_choice_used: number;
  free_choice_limit: number;
  professional_used: number;
  professional_limit: number;
}

export interface StudentProfile {
  faculty: string | null;
  specialty: string | null;
  course_year: 1 | 2 | 3 | 4 | null;
  course_year_source: "self_declared" | "admin" | "saz_sync" | null;
  onboarding_required: boolean;
  can_create_plan: boolean;
  load_levels_mode: "manual" | "auto";
  credits: Credits;
  saz_synced_at: string | null;
}

export interface Me {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  student: StudentProfile | null;
}
