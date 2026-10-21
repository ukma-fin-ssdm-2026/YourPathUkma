// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: admin.test.tsx.
import { NavLink, Outlet, useLocation } from "react-router";

export const ADMIN_SECTIONS: { to: string; label: string; end?: boolean }[] = [
  { to: "/admin", label: "Огляд", end: true },
  { to: "/admin/moderation", label: "Модерація" },
  { to: "/admin/sync", label: "Синхронізація" },
  { to: "/admin/users", label: "Користувачі" },
  { to: "/admin/directions", label: "Напрямки" },
  { to: "/admin/audit", label: "Журнал дій" },
];

export function AdminLayout() {
  const { pathname } = useLocation();
  return (
    <div className="flex flex-col gap-6 md:flex-row">
      <nav
        aria-label="Розділи адмінки"
        className="flex gap-1 overflow-x-auto md:w-[220px] md:shrink-0 md:flex-col"
      >
        {ADMIN_SECTIONS.map((section) => (
          <NavLink
            key={section.to}
            to={section.to}
            end={section.end}
            className={({ isActive }) =>
              "whitespace-nowrap rounded-[10px] px-3.5 py-2 font-medium transition-colors duration-150 ease-out " +
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt " +
              (isActive ? "bg-info-bg text-cobalt" : "text-ink-2 hover:bg-surface hover:text-ink")
            }
          >
            {section.label}
          </NavLink>
        ))}
      </nav>
      <div key={pathname} className="rise min-w-0 flex-1">
        <Outlet />
      </div>
    </div>
  );
}
