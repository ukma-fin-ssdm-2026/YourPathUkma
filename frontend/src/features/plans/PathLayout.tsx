// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: plans.test.tsx.
// Codex узгодив дії з доступністю конструктора. Перевірка — фронтенд-тести.
import { NavLink, Outlet, useLocation } from "react-router";
import { useMe } from "../profile/useMe";

const TABS = [
  { to: "/path/plan", label: "Індивідуальний план" },
  { to: "/path/saved", label: "Збережені плани" },
  { to: "/path/create", label: "Створити план" },
];

/** Підвкладки розділу «Науковий шлях». */
export function PathLayout() {
  const { pathname } = useLocation();
  const canCreate = useMe().data?.student?.can_create_plan === true;
  return (
    <div>
      <nav aria-label="Науковий шлях" className="mb-5 flex flex-wrap gap-1.5">
        {TABS.filter((tab) => tab.to !== "/path/create" || canCreate).map((tab) => (
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
      <div key={pathname} className="fade-in">
        <Outlet />
      </div>
    </div>
  );
}
