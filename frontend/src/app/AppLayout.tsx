// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: AppLayout.test.tsx.
import { Link, NavLink, Outlet } from "react-router";
import { Button } from "../ui/Button";
import { initials } from "../lib/initials";
import { NAV_ITEMS, type Role } from "./nav";

export function AppLayout({
  role,
  userName,
  onSignOut,
}: {
  role: Role;
  userName: string;
  onSignOut?: () => void;
}) {
  const items = NAV_ITEMS.filter((item) => !item.adminOnly || role === "admin");
  return (
    <div className="min-h-screen bg-paper text-ink">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-20 focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2 focus:font-semibold focus:shadow-lg"
      >
        Перейти до вмісту
      </a>
      <header className="border-b border-rule bg-surface">
        <div className="mx-auto flex h-[60px] max-w-[1160px] items-center gap-8 px-6">
          <Link to="/" className="font-display text-[15px] font-semibold">
            YourPath
          </Link>
          <nav aria-label="Основна навігація" className="flex h-full min-w-0 gap-0.5 overflow-x-auto">
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
          <div className="ml-auto flex min-w-0 items-center gap-2.5 font-medium">
            <span className="min-w-0 max-w-[180px] truncate">{userName}</span>
            <span
              aria-hidden="true"
              className="grid size-8 shrink-0 place-items-center rounded-full bg-ink text-xs text-surface"
            >
              {initials(userName)}
            </span>
            {onSignOut && (
              <Button variant="ghost" size="sm" className="shrink-0" onClick={onSignOut}>
                Вийти
              </Button>
            )}
          </div>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="outline-none mx-auto max-w-[1160px] px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
