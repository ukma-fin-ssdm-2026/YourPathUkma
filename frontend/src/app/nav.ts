// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: AppLayout.test.tsx.
import type { UserRole } from "../api/types";

export type Role = UserRole;

export const NAV_ITEMS: { to: string; label: string; adminOnly?: boolean }[] = [
  { to: "/", label: "Профіль" },
  { to: "/path/plan", label: "Науковий шлях" },
  { to: "/catalog", label: "Каталог" },
  { to: "/admin", label: "Адмінка", adminOnly: true },
];
