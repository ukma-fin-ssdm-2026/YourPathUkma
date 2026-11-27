// Використання ШІ: Codex виправив #220; перевірка: регресії Vitest, ESLint і TypeScript.
// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: auth-ui.test.tsx.
import { toast } from "sonner";
import { useNavigate } from "react-router";
import { signOut, useSession } from "../auth/session";
import { AppLayout } from "./AppLayout";

/** Підставляє в AppLayout роль, ім'я й дію «Вийти» з поточної сесії. */
export function ConnectedLayout() {
  const user = useSession((s) => s.user);
  const navigate = useNavigate();
  if (!user) return null;
  async function logout() {
    const confirmed = await signOut();
    navigate("/login", { replace: true });
    if (!confirmed) {
      toast.warning(
        "Вихід не підтверджено сервером. Сесія може відновитися після перезавантаження.",
        {
          duration: Infinity,
          action: {
            label: "Повторити вихід",
            onClick: () => {
              void logout();
            },
          },
        },
      );
    }
  }
  return (
    <AppLayout
      role={user.role}
      userName={user.full_name}
      onSignOut={() => {
        void logout();
      }}
    />
  );
}
