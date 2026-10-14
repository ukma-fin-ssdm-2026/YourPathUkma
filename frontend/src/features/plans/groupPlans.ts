// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: plans.test.tsx.
import type { PlanResponse } from "../../api/types";

export interface PlanGroup {
  course: number;
  academic_year: number;
  plans: PlanResponse[];
}

/** Групи за навчальним роком: новіші зверху; усередині групи плани за id за спаданням. */
export function groupPlansByCourse(plans: PlanResponse[]): PlanGroup[] {
  const byYear = new Map<number, PlanGroup>();
  for (const plan of plans) {
    const group = byYear.get(plan.academic_year);
    if (group) group.plans.push(plan);
    else byYear.set(plan.academic_year, { course: plan.course, academic_year: plan.academic_year, plans: [plan] });
  }
  return [...byYear.values()]
    .sort((a, b) => b.academic_year - a.academic_year)
    .map((group) => ({ ...group, plans: [...group.plans].sort((a, b) => b.id - a.id) }));
}

export function courseHeading(group: { course: number; academic_year: number }): string {
  return `${group.course} курс · ${group.academic_year}/${group.academic_year + 1}`;
}
