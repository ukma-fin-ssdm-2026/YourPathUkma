// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: lib.test.ts.
const formatter = new Intl.NumberFormat("uk-UA", { maximumFractionDigits: 1 });

/** 118.5 → «118,5», 60 → «60». */
export function formatCredits(value: number): string {
  return formatter.format(value);
}

/** Частка від ліміту, 0-100; при нульовому ліміті 0, а не NaN. */
export function creditsPercent(used: number, limit: number): number {
  if (limit <= 0) return 0;
  return Math.min(100, Math.max(0, (used / limit) * 100));
}

/** «кредит» / «кредити» / «кредитів» за правилами української мови; дробові числа йдуть як «кредити». */
export function creditsWord(value: number): string {
  if (!Number.isInteger(value)) return "кредити";
  const lastTwo = value % 100;
  const last = value % 10;
  if (lastTwo >= 11 && lastTwo <= 14) return "кредитів";
  if (last === 1) return "кредит";
  if (last >= 2 && last <= 4) return "кредити";
  return "кредитів";
}
