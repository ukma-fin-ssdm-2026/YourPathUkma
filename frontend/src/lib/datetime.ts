// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: sync.test.tsx.
const formatter = new Intl.DateTimeFormat("uk-UA", { dateStyle: "short", timeStyle: "short" });

/** «08.10.2026, 12:00» за місцевим часом; порожнє значення дає «—». */
export function formatDateTime(iso: string | null): string {
  return iso ? formatter.format(new Date(iso)) : "—";
}
