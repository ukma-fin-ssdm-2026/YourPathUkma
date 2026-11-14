// Використання ШІ: Codex додав перевірку параметрів плану. Перевірка: тести конструктора, документа і побажань.
import type { ConfigResponse } from "../api/types";

/** Рік за замовчуванням обмежено діапазоном з /config. */
export function defaultPlanYear(now: Date, min: number, max: number): number {
  return Math.min(max, Math.max(min, now.getFullYear()));
}

export function parsePlanId(raw: string | null): number | null {
  if (raw === null || !/^\d+$/.test(raw)) return null;
  const value = Number(raw);
  return Number.isSafeInteger(value) && value > 0 ? value : null;
}

export function planYearFromParam(raw: string | null, limits?: ConfigResponse["limits"]): number {
  const min = limits?.academic_year_min ?? 2024;
  const max = limits?.academic_year_max ?? 2030;
  const year = parsePlanId(raw);
  return year !== null && year >= min && year <= max ? year : defaultPlanYear(new Date(), min, max);
}
