// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: auth-ui.test.tsx.
import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router";
import { ApiError } from "../api/errors";
import type { LoginErrorInfo } from "./LoginPage";
import { completeLogin } from "./login";
import { useSession } from "./session";

export function CallbackPage() {
  const navigate = useNavigate();
  const { search } = useLocation();
  // Код входу одноразовий: StrictMode не повинен обміняти його вдруге.
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    completeLogin(search)
      .then((auth) => {
        useSession.getState().setAuthenticated(auth);
        navigate("/", { replace: true });
      })
      .catch((e: unknown) => {
        const failure =
          e instanceof ApiError ? e : new ApiError(0, "UNKNOWN", "Не вдалося завершити вхід");
        const error: LoginErrorInfo = {
          code: failure.code,
          message: failure.message,
          requestId: failure.requestId,
        };
        navigate("/login", { replace: true, state: { error } });
      });
  }, [navigate, search]);

  return (
    <p role="status" className="p-8 text-ink-2">
      Входимо…
    </p>
  );
}
