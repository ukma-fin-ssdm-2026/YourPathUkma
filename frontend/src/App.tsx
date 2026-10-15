// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: App.test.tsx, npm run build.
import { createBrowserRouter } from "react-router";
import { RouterProvider } from "react-router/dom";
import { appRoutes } from "./app/routes";

const router = createBrowserRouter(appRoutes);

export function App() {
  return <RouterProvider router={router} />;
}
