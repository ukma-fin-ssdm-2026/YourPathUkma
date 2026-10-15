// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm run typecheck, ручний запуск dev.
import type { RouteObject } from "react-router";
import { AppLayout } from "./AppLayout";

export function PlaceholderPage({ title }: { title: string }) {
  return (
    <div>
      <h1 className="font-display text-[22px]">{title}</h1>
      <p className="mt-2 text-ink-2">Екран у розробці.</p>
    </div>
  );
}

// Роль і ім'я поки сталі; реальні значення приходять із автентифікації в наступному плані.
export const appRoutes: RouteObject[] = [
  { path: "/login", element: <PlaceholderPage title="Вхід" /> },
  { path: "/onboarding", element: <PlaceholderPage title="Онбординг" /> },
  {
    element: <AppLayout role="student" userName="Студент" />,
    children: [
      { path: "/", element: <PlaceholderPage title="Профіль" /> },
      { path: "/path/plan", element: <PlaceholderPage title="Індивідуальний план" /> },
      { path: "/path/saved", element: <PlaceholderPage title="Збережені плани" /> },
      { path: "/path/create", element: <PlaceholderPage title="Створити план" /> },
      { path: "/path/create/document", element: <PlaceholderPage title="Документ деканату" /> },
      { path: "/catalog", element: <PlaceholderPage title="Каталог" /> },
      { path: "/admin", element: <PlaceholderPage title="Адмінка" /> },
    ],
  },
];
