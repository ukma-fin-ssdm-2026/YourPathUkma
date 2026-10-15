// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: auth-ui.test.tsx.
import { Navigate, Outlet } from "react-router";
import { useSession } from "./session";

/** Layout-маршрут: пускає лише автентифікованих; поки сесія відновлюється, чекає, а не редіректить. */
export function RequireAuth() {
  const status = useSession((s) => s.status);
  if (status === "loading") {
    return (
      <p role="status" className="p-8 text-ink-2">
        Завантаження…
      </p>
    );
  }
  if (status === "anonymous") return <Navigate to="/login" replace />;
  return <Outlet />;
}

/** Лише для адміністратора. Це UI-обмеження, справжній захист на сервері. */
export function RequireAdmin() {
  const role = useSession((s) => s.user?.role);
  if (role !== "admin") return <Navigate to="/" replace />;
  return <Outlet />;
}
