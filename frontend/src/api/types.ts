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

export type AcademicCategory = "normative" | "professional" | "free_choice";

export interface AcademicRecord {
  id: number;
  academic_year: number;
  course_year: number;
  course_id: number | null;
  title: string;
  trimester: number;
  credits: number;
  category: AcademicCategory;
  source: string;
  verified: boolean;
}

export interface AcademicYear {
  academic_year: number;
  course_year: number;
  total_credits: number;
  records: AcademicRecord[];
}

// ✅-моделі беруться зі згенерованої схеми OpenAPI (`npm run gen:api`).
import type { components } from "./generated/schema";

export type Discipline = components["schemas"]["Discipline"];
export type Direction = components["schemas"]["Direction"];
export type PaginationInfo = components["schemas"]["PaginationInfo"];
export type PaginatedDisciplinesResponse = components["schemas"]["PaginatedDisciplinesResponse"];
export type PlanResponse = components["schemas"]["PlanResponse"];
export type PaginatedPlansResponse = components["schemas"]["PaginatedPlansResponse"];

export type ParseStatus = "pending" | "parsed" | "failed";

export interface NormativeCourse {
  course_id: number | null;
  raw_title: string;
  trimester: 1 | 2 | 3;
  credits: number;
}

export interface DeaneryDocument {
  id: number;
  academic_year: number;
  original_filename: string;
  mime_type: "pdf" | "docx";
  size_bytes: number;
  parse_status: ParseStatus;
  parse_error: string | null;
  uploaded_at: string;
  normative_courses: NormativeCourse[];
}

export type LoadLevels = Partial<Record<"autumn" | "spring" | "summer", LoadLevel>>;

export interface Instructor {
  id: number;
  full_name: string;
}

export interface Preferences {
  academic_year: number;
  load_levels: LoadLevels;
  direction_ids: number[];
  include_free_electives: boolean;
  preferred_instructor_ids: number[];
  unwanted_instructor_ids: number[];
  wants_certificate: boolean;
  certificate_program_id: number | null;
  updated_at?: string;
}

export type PlanItem = components["schemas"]["PlanItem"];
export type PlanValidationResponse = components["schemas"]["PlanValidationResponse"];
export type RuleIssue = components["schemas"]["RuleIssue"];
export type PlanSummary = components["schemas"]["PlanSummary"];

// ---------- Адмінка (🟡), contract.md §4 ----------
export interface SyncJob {
  id: number;
  source: "saz_catalog" | "faculty_certificates";
  initiator: "admin" | "scheduler";
  initiated_by: { id: number; full_name: string } | null;
  status: "queued" | "running" | "succeeded" | "failed";
  started_at: string;
  finished_at: string | null;
  added_count: number;
  updated_count: number;
  error_message: string | null;
}

export interface ModerationItem {
  id: number;
  sync_job_id: number;
  course_id: number | null;
  change_type: "add" | "update" | "remove";
  payload: Record<string, unknown>;
  diff: Record<string, { old: unknown; new: unknown }> | null;
  status: "pending" | "approved" | "rejected";
  reviewed_by: { id: number; full_name: string } | null;
  reviewed_at: string | null;
}

export interface BulkReviewResult {
  approved: number[];
  rejected: number[];
  skipped: { id: number; code: string }[];
}

export interface AdminUser {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  created_at: string;
  last_login_at: string | null;
  student: null | {
    specialty: string | null;
    course_year: 1 | 2 | 3 | 4 | null;
    course_year_source: "self_declared" | "admin" | "saz_sync" | null;
  };
}

export interface AdminUserPatch {
  role?: UserRole;
  student?: { course_year?: 1 | 2 | 3 | 4; specialty?: string };
}

export interface DirectionInput {
  name: string;
  description?: string | null;
}

export interface AuditLogEntry {
  id: number;
  actor: { id: number; full_name: string } | null;
  action: string;
  object_type: string;
  object_id: number;
  outcome: "allowed" | "denied";
  ip: string;
  created_at: string;
  old_value?: unknown;
  new_value?: unknown;
}
