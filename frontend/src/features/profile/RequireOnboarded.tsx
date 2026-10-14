// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: onboarding.test.tsx.
import { Navigate, Outlet } from "react-router";
import { useMe } from "./useMe";

/** Поки студент не вказав курс і спеціальність, ведемо його на онбординг (сервер теж поверне 409). */
export function RequireOnboarded() {
  const me = useMe();
  if (me.isError) {
    return (
      <p role="alert" className="p-8 text-bad">
        Не вдалося завантажити профіль. Оновіть сторінку.
      </p>
    );
  }
  if (!me.data) {
    return (
      <p role="status" className="p-8 text-ink-2">
        Завантаження…
      </p>
    );
  }
  if (me.data.student?.onboarding_required) return <Navigate to="/onboarding" replace />;
  return <Outlet />;
}
