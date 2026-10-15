// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: session.test.ts.
import { create } from "zustand";
import { configureAuth, request } from "../api/client";
import { queryClient } from "../api/queryClient";
import { setAccessToken } from "../api/token";
import type { AuthResponse, AuthUser } from "../api/types";

interface SessionState {
  status: "loading" | "authenticated" | "anonymous";
  user: AuthUser | null;
  setAuthenticated: (auth: AuthResponse) => void;
  setAnonymous: () => void;
}

export const useSession = create<SessionState>((set) => ({
  status: "loading",
  user: null,
  setAuthenticated: (auth) => {
    setAccessToken(auth.access_token);
    set({ status: "authenticated", user: auth.user });
  },
  setAnonymous: () => {
    setAccessToken(null);
    queryClient.clear();
    set({ status: "anonymous", user: null });
  },
}));

async function refreshRequest(): Promise<AuthResponse | null> {
  try {
    return await request<AuthResponse>("/auth/refresh", { method: "POST", auth: false });
  } catch {
    return null;
  }
}

/** Відновлює сесію з refresh-cookie при старті застосунку. */
export async function restoreSession(): Promise<void> {
  const auth = await refreshRequest();
  if (auth) useSession.getState().setAuthenticated(auth);
  else useSession.getState().setAnonymous();
}

export async function signOut(): Promise<void> {
  try {
    await request("/auth/logout", { method: "POST", auth: false });
  } catch {
    // сервер недоступний: сесію на клієнті все одно завершуємо
  }
  useSession.getState().setAnonymous();
}

/** Підключає refresh на 401 і скидання сесії до клієнта API. */
export function installAuth(): void {
  configureAuth({
    refresh: async () => {
      const auth = await refreshRequest();
      if (!auth) return null;
      useSession.setState({ status: "authenticated", user: auth.user });
      return auth.access_token;
    },
    onAuthLost: () => useSession.getState().setAnonymous(),
  });
}
