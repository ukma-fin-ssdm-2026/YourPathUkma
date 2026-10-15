// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: AppLayout.test.tsx.
import { Link, NavLink, Outlet } from "react-router";
import { NAV_ITEMS, type Role } from "./nav";

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]!.toUpperCase())
    .join("");
}

export function AppLayout({ role, userName }: { role: Role; userName: string }) {
  const items = NAV_ITEMS.filter((item) => !item.adminOnly || role === "admin");
  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="border-b border-rule bg-surface">
        <div className="mx-auto flex h-[60px] max-w-[1160px] items-center gap-8 px-6">
          <Link to="/" className="font-display text-[15px] font-semibold">
            YourPath
          </Link>
          <nav aria-label="Основна навігація" className="flex h-full gap-0.5">
            {items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  "-mb-px flex items-center border-b-[3px] px-3.5 font-medium transition-colors duration-150 ease-out " +
                  "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-cobalt " +
                  (isActive
                    ? "border-cobalt text-ink"
                    : "border-transparent text-ink-2 hover:text-ink")
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2.5 font-medium">
            <span>{userName}</span>
            <span
              aria-hidden="true"
              className="grid size-8 place-items-center rounded-full bg-ink text-xs text-surface"
            >
              {initials(userName)}
            </span>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1160px] px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
