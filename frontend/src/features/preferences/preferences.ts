// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: preferences-data.test.tsx.
import type { LoadLevels, Preferences } from "../../api/types";

export const MAX_DIRECTIONS = 3;

export function defaultPreferences(year: number): Preferences {
  return {
    academic_year: year,
    load_levels: { autumn: "medium", spring: "medium", summer: "medium" },
    direction_ids: [],
    include_free_electives: true,
    preferred_instructor_ids: [],
    unwanted_instructor_ids: [],
    wants_certificate: false,
    certificate_program_id: null,
  };
}

/** Додає або знімає напрямок; понад `max` додати не можна. */
export function toggleDirection(ids: number[], id: number, max = MAX_DIRECTIONS): number[] {
  if (ids.includes(id)) return ids.filter((value) => value !== id);
  return ids.length < max ? [...ids, id] : ids;
}

type InstructorLists = Pick<Preferences, "preferred_instructor_ids" | "unwanted_instructor_ids">;

/** Переносить викладача в потрібний список (або прибирає, якщо `to` дорівнює null): він ніколи не в обох. */
export function moveInstructor(
  lists: InstructorLists,
  id: number,
  to: "preferred" | "unwanted" | null,
): InstructorLists {
  const preferred = lists.preferred_instructor_ids.filter((value) => value !== id);
  const unwanted = lists.unwanted_instructor_ids.filter((value) => value !== id);
  if (to === "preferred") preferred.push(id);
  if (to === "unwanted") unwanted.push(id);
  return { preferred_instructor_ids: preferred, unwanted_instructor_ids: unwanted };
}

export function hasLowLoad(levels: LoadLevels): boolean {
  return Object.values(levels).includes("low");
}
