// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: auth-ui.test.tsx.
import { useNavigate } from "react-router";
import { signOut, useSession } from "../auth/session";
import { AppLayout } from "./AppLayout";

/** Підставляє в AppLayout роль, ім'я й дію «Вийти» з поточної сесії. */
export function ConnectedLayout() {
  const user = useSession((s) => s.user);
  const navigate = useNavigate();
  if (!user) return null;
  return (
    <AppLayout
      role={user.role}
      userName={user.full_name}
      onSignOut={async () => {
        await signOut();
        navigate("/login", { replace: true });
      }}
    />
  );
}
