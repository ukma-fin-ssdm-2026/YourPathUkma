// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm run typecheck, auth-ui.test.tsx.
import type { RouteObject } from "react-router";
import { CallbackPage } from "../auth/CallbackPage";
import { LoginPage } from "../auth/LoginPage";
import { RequireAdmin, RequireAuth } from "../auth/RequireAuth";
import { ConnectedLayout } from "./ConnectedLayout";

export function PlaceholderPage({ title }: { title: string }) {
  return (
    <div>
      <h1 className="font-display text-[22px]">{title}</h1>
      <p className="mt-2 text-ink-2">Екран у розробці.</p>
    </div>
  );
}

export const appRoutes: RouteObject[] = [
  { path: "/login", element: <LoginPage /> },
  { path: "/auth/callback", element: <CallbackPage /> },
  {
    element: <RequireAuth />,
    children: [
      { path: "/onboarding", element: <PlaceholderPage title="Онбординг" /> },
      {
        element: <ConnectedLayout />,
        children: [
          { path: "/", element: <PlaceholderPage title="Профіль" /> },
          { path: "/path/plan", element: <PlaceholderPage title="Індивідуальний план" /> },
          { path: "/path/saved", element: <PlaceholderPage title="Збережені плани" /> },
          { path: "/path/create", element: <PlaceholderPage title="Створити план" /> },
          { path: "/path/create/document", element: <PlaceholderPage title="Документ деканату" /> },
          { path: "/catalog", element: <PlaceholderPage title="Каталог" /> },
          {
            element: <RequireAdmin />,
            children: [{ path: "/admin", element: <PlaceholderPage title="Адмінка" /> }],
          },
        ],
      },
    ],
  },
];
