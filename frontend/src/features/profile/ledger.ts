// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: profile.test.tsx.
import type { AcademicCategory, AcademicRecord } from "../../api/types";

export interface LedgerRow {
  normative: number;
  professional: number;
  free_choice: number;
  empty: number;
}

export function sumByCategory(records: AcademicRecord[]): Record<AcademicCategory, number> {
  const totals: Record<AcademicCategory, number> = {
    normative: 0,
    professional: 0,
    free_choice: 0,
  };
  for (const record of records) totals[record.category] += record.credits;
  return totals;
}

/**
 * Скільки клітинок кожної категорії в рядку року (1 клітинка = 1 кредит).
 * Межі категорій рахуються накопичувально, щоб дробові кредити не губились при округленні.
 */
export function buildLedgerRow(records: AcademicRecord[], perYear = 60): LedgerRow {
  const totals = sumByCategory(records);
  const cap = (value: number) => Math.min(perYear, Math.round(value));
  const normativeEnd = cap(totals.normative);
  const professionalEnd = Math.max(normativeEnd, cap(totals.normative + totals.professional));
  const freeEnd = Math.max(
    professionalEnd,
    cap(totals.normative + totals.professional + totals.free_choice),
  );
  return {
    normative: normativeEnd,
    professional: professionalEnd - normativeEnd,
    free_choice: freeEnd - professionalEnd,
    empty: perYear - freeEnd,
  };
}
