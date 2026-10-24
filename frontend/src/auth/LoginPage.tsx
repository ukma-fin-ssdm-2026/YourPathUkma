// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: auth-ui.test.tsx.
import { useState } from "react";
import { Navigate, useLocation } from "react-router";
import { AuthShell } from "./AuthShell";
import { startLogin } from "./login";
import { useSession } from "./session";

export interface LoginErrorInfo {
  code: string;
  message: string;
  requestId: string | null;
}

function errorText(error: LoginErrorInfo): string {
  if (error.code === "DOMAIN_NOT_ALLOWED") {
    return "Цей обліковий запис не належить до НаУКМА. Увійдіть з пошти @ukma.edu.ua.";
  }
  return error.message;
}

function MicrosoftLogo() {
  return (
    <span aria-hidden="true" className="grid grid-cols-[11px_11px] gap-0.5">
      <i className="size-[11px] bg-[#f25022]" />
      <i className="size-[11px] bg-[#7fba00]" />
      <i className="size-[11px] bg-[#00a4ef]" />
      <i className="size-[11px] bg-[#ffb900]" />
    </span>
  );
}

export function LoginPage({ onLogin = () => startLogin() }: { onLogin?: () => Promise<void> }) {
  const status = useSession((s) => s.status);
  const location = useLocation();
  const [localError, setLocalError] = useState<LoginErrorInfo | null>(null);
  const [busy, setBusy] = useState(false);

  if (status === "authenticated") return <Navigate to="/" replace />;

  const routed = (location.state as { error?: LoginErrorInfo } | null)?.error ?? null;
  const error = localError ?? routed;
  const failed = error !== null && error.code !== "OAUTH_NOT_CONFIGURED";

  async function handleLogin() {
    setBusy(true);
    setLocalError(null);
    try {
      await onLogin();
    } catch (e) {
      const info = e as { code?: string; message?: string; requestId?: string | null };
      setLocalError({
        code: info.code ?? "UNKNOWN",
        message: info.message ?? "Не вдалося почати вхід",
        requestId: info.requestId ?? null,
      });
      setBusy(false);
    }
  }

  return (
    <AuthShell
      heading="Ваш шлях до 240 кредитів"
      lead="Обирайте вибіркові дисципліни, стежте за кредитами й порівнюйте варіанти плану."
      showLedger
    >
      <h2 className="mb-2 font-display text-[28px] leading-tight">
        {failed ? "Не вдалося увійти" : "Вхід у застосунок"}
      </h2>
      <p className="mb-8 max-w-[40ch] text-[17px] text-ink-2">
        Використайте робочий обліковий запис Microsoft 365 від НаУКМА.
      </p>
      {error && (
        <div
          role="alert"
          className="mb-5 max-w-[420px] rounded-[10px] bg-bad-bg px-4 py-3.5 text-bad"
        >
          {errorText(error)}
        </div>
      )}
      <button
        type="button"
        onClick={handleLogin}
        disabled={busy}
        className="flex w-full max-w-[420px] cursor-pointer items-center justify-center gap-3.5 rounded-xl border border-rule bg-white px-5 py-4 text-[17px] font-semibold text-[#1b1b1b] transition-[transform,translate,box-shadow] duration-200 ease-out hover:-translate-y-0.5 hover:shadow-lg active:scale-[.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt disabled:cursor-wait disabled:opacity-70"
      >
        <MicrosoftLogo />
        {failed ? "Обрати інший обліковий запис" : "Увійти через Microsoft"}
      </button>
      {error?.requestId && (
        <p className="mt-4 text-sm text-ink-2">Код помилки: {error.requestId}</p>
      )}
      <p className="mt-5 max-w-[42ch] text-sm text-ink-2">
        Потрібна пошта в домені <b>ukma.edu.ua</b>. Ми не бачимо й не зберігаємо ваш пароль.
      </p>
    </AuthShell>
  );
}
