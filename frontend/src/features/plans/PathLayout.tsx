// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: plans.test.tsx.
import { NavLink, Outlet, useLocation } from "react-router";

const TABS = [
  { to: "/path/plan", label: "Індивідуальний план" },
  { to: "/path/saved", label: "Збережені плани" },
  { to: "/path/create", label: "Створити план" },
];

/** Підвкладки розділу «Науковий шлях». */
export function PathLayout() {
  const { pathname } = useLocation();
  return (
    <div>
      <nav aria-label="Науковий шлях" className="mb-5 flex flex-wrap gap-1.5">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end
            className={({ isActive }) =>
              "rounded-full px-3.5 py-1.5 font-medium transition-colors duration-150 ease-out focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt " +
              (isActive ? "bg-cobalt text-on-accent" : "text-ink-2 hover:text-ink")
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <div key={pathname} className="rise">
        <Outlet />
      </div>
    </div>
  );
}
