// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: AppLayout.test.tsx.
export type Role = "student" | "admin";

export const NAV_ITEMS: { to: string; label: string; adminOnly?: boolean }[] = [
  { to: "/", label: "Профіль" },
  { to: "/path/plan", label: "Науковий шлях" },
  { to: "/catalog", label: "Каталог" },
  { to: "/admin", label: "Адмінка", adminOnly: true },
];
