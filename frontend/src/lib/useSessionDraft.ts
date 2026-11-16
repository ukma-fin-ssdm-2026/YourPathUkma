// Використання ШІ: Codex додав відновлення чернеток у вкладці. Перевірка: save.test.tsx і form.test.tsx.
import { useState } from "react";
import { useSession } from "../auth/session";

function readDraft<T>(key: string | null): T | null {
  if (key === null) return null;
  try {
    const stored = sessionStorage.getItem(key);
    return stored === null ? null : (JSON.parse(stored) as T);
  } catch {
    return null;
  }
}

export function useSessionDraft<T>(scope: string): [T | null, (value: T | null) => void] {
  const userId = useSession((session) => session.user?.id);
  const key = userId === undefined ? null : `yourpath:draft:v1:${userId}:${scope}`;
  const [state, setState] = useState(() => ({ key, scope, value: readDraft<T>(key) }));
  const current =
    state.key === key && state.scope === scope ? state : { key, scope, value: readDraft<T>(key) };
  if (current !== state) setState(current);

  function setDraft(value: T | null) {
    if (key !== null) {
      try {
        if (value === null) sessionStorage.removeItem(key);
        else sessionStorage.setItem(key, JSON.stringify(value));
      } catch {
        // Пам’ять компонента доступна і коли браузер обмежив сховище вкладки.
      }
    }
    setState({ key, scope, value });
  }

  return [current.value, setDraft];
}
