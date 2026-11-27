// Використання ШІ: Codex виправив #220; перевірка: регресії Vitest, ESLint і TypeScript.
// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: sync.test.tsx.
const formatter = new Intl.DateTimeFormat("uk-UA", { dateStyle: "short", timeStyle: "short" });

/** «08.10.2026, 12:00» за місцевим часом; порожнє значення дає «—». */
export function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : formatter.format(date);
}
