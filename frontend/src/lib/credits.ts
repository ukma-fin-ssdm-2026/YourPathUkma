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
