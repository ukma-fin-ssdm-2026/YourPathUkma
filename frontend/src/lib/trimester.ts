// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: lib.test.ts.
export type Trimester = 1 | 2 | 3;
export type TrimesterKey = "autumn" | "spring" | "summer";

const KEYS: Record<Trimester, TrimesterKey> = { 1: "autumn", 2: "spring", 3: "summer" };
const LABELS: Record<Trimester, string> = { 1: "Осінь", 2: "Весна", 3: "Літо" };

export function trimesterKey(trimester: Trimester): TrimesterKey {
  return KEYS[trimester];
}

export function trimesterFromKey(key: TrimesterKey): Trimester {
  return ({ autumn: 1, spring: 2, summer: 3 } as const)[key];
}

export function trimesterLabel(trimester: Trimester): string {
  return LABELS[trimester];
}
