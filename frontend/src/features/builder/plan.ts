// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: plan.test.ts.
// Чиста логіка плану без React: UI лише показує її результат. Остаточні правила перевіряє сервер.
import type { Discipline, LoadLevel, LoadLevels, PlanItem } from "../../api/types";
import type { Trimester } from "../../lib/trimester";

export const MAX_ITEMS = 30;
export const FREE_LIMIT = 25;
export const MIN_YEAR_CREDITS = 57;

export interface BuilderPlan {
  academic_year: number;
  course: 2 | 3 | 4;
  load_levels: Required<LoadLevels>;
  items: PlanItem[];
}

export type AddBlock = "duplicate" | "limit" | "normative";

/** Контракт §3.3: вільний вибір, якщо напрямків немає або жоден з напрямків студента не збігається. */
export function isFreeElective(discipline: Discipline, studentDirections: string[]): boolean {
  const own = discipline.directions ?? [];
  if (own.length === 0) return true;
  const mine = studentDirections.map((name) => name.toLowerCase());
  return !own.some((name) => mine.includes(name.toLowerCase()));
}

export function toPlanItem(discipline: Discipline, studentDirections: string[]): PlanItem {
  return {
    course_id: discipline.id,
    title: discipline.title,
    trimester: discipline.trimester,
    credits: discipline.credits,
    is_free_elective: isFreeElective(discipline, studentDirections),
  };
}

export function canAdd(
  plan: BuilderPlan,
  discipline: Discipline,
): { ok: true } | { ok: false; reason: AddBlock } {
  if (discipline.discipline_type === "normative") return { ok: false, reason: "normative" };
  if (plan.items.some((item) => item.course_id === discipline.id))
    return { ok: false, reason: "duplicate" };
  if (plan.items.length >= MAX_ITEMS) return { ok: false, reason: "limit" };
  return { ok: true };
}

export function blockMessage(reason: AddBlock): string {
  switch (reason) {
    case "duplicate":
      return "Ця дисципліна вже в плані";
    case "limit":
      return `У плані може бути не більше ${MAX_ITEMS} дисциплін`;
    case "normative":
      return "Нормативні дисципліни додає деканат";
  }
}

/** Додає дисципліну; якщо додати не можна, повертає той самий об'єкт плану. */
export function addDiscipline(
  plan: BuilderPlan,
  discipline: Discipline,
  studentDirections: string[],
): BuilderPlan {
  if (!canAdd(plan, discipline).ok) return plan;
  return { ...plan, items: [...plan.items, toPlanItem(discipline, studentDirections)] };
}

export function removeCourse(plan: BuilderPlan, courseId: number): BuilderPlan {
  return { ...plan, items: plan.items.filter((item) => item.course_id !== courseId) };
}

export function setLoad(
  plan: BuilderPlan,
  season: "autumn" | "spring" | "summer",
  level: LoadLevel,
): BuilderPlan {
  return { ...plan, load_levels: { ...plan.load_levels, [season]: level } };
}

export function summarize(items: PlanItem[]): {
  total: number;
  free: number;
  byTrimester: Record<Trimester, number>;
} {
  const byTrimester: Record<Trimester, number> = { 1: 0, 2: 0, 3: 0 };
  let total = 0;
  let free = 0;
  for (const item of items) {
    total += item.credits;
    if (item.is_free_elective) free += item.credits;
    byTrimester[item.trimester as Trimester] += item.credits;
  }
  return { total, free, byTrimester };
}

const WHEN: Record<Trimester, string> = { 1: "восени", 2: "навесні", 3: "влітку" };

/** Дисципліна має лише один триместр (збіг з каталогом), тож у чужу колонку її не покласти. */
export function dropVerdict(
  discipline: Discipline,
  column: Trimester,
): { ok: true } | { ok: false; message: string } {
  if (discipline.trimester === column) return { ok: true };
  return {
    ok: false,
    message: `Ця дисципліна викладається ${WHEN[discipline.trimester as Trimester]}`,
  };
}

export function trimesterOf(item: PlanItem): Trimester {
  return item.trimester as Trimester;
}
