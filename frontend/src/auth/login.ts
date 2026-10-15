// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: login.test.ts.
// Вхід через Microsoft 365: Authorization Code + PKCE. Обмін коду робить бекенд (POST /auth/microsoft;
// назва ендпоінта це припущення, див. спеку §4).
import { request } from "../api/client";
import { ApiError } from "../api/errors";
import { setAccessToken } from "../api/token";
import type { AuthResponse } from "../api/types";
import { codeChallenge, randomUrlSafe } from "./pkce";

const VERIFIER_KEY = "pkce_verifier";
const STATE_KEY = "oauth_state";

export interface LoginEnv {
  clientId: string;
  tenant: string;
  origin: string;
}

function loginEnv(): LoginEnv {
  return {
    clientId: import.meta.env.VITE_MS_CLIENT_ID ?? "",
    tenant: import.meta.env.VITE_MS_TENANT || "organizations",
    origin: window.location.origin,
  };
}

export function buildAuthorizeUrl(env: LoginEnv, p: { state: string; challenge: string }): string {
  const url = new URL(`https://login.microsoftonline.com/${env.tenant}/oauth2/v2.0/authorize`);
  url.searchParams.set("client_id", env.clientId);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("redirect_uri", `${env.origin}/auth/callback`);
  url.searchParams.set("scope", "openid email profile");
  url.searchParams.set("response_mode", "query");
  url.searchParams.set("state", p.state);
  url.searchParams.set("code_challenge", p.challenge);
  url.searchParams.set("code_challenge_method", "S256");
  return url.toString();
}

export async function startLogin(
  navigate: (url: string) => void = (url) => window.location.assign(url),
): Promise<void> {
  const env = loginEnv();
  if (!env.clientId) {
    throw new ApiError(0, "OAUTH_NOT_CONFIGURED", "Вхід не налаштовано: немає VITE_MS_CLIENT_ID");
  }
  const verifier = randomUrlSafe(32);
  const state = randomUrlSafe(16);
  const challenge = await codeChallenge(verifier);
  sessionStorage.setItem(VERIFIER_KEY, verifier);
  sessionStorage.setItem(STATE_KEY, state);
  navigate(buildAuthorizeUrl(env, { state, challenge }));
}

export async function completeLogin(search: string): Promise<AuthResponse> {
  const params = new URLSearchParams(search);
  const expectedState = sessionStorage.getItem(STATE_KEY);
  const verifier = sessionStorage.getItem(VERIFIER_KEY);
  try {
    if (params.get("error")) {
      throw new ApiError(0, "OAUTH_ERROR", "Вхід скасовано або відхилено");
    }
    if (!expectedState || params.get("state") !== expectedState) {
      throw new ApiError(0, "OAUTH_STATE_MISMATCH", "Сесія входу застаріла. Спробуйте ще раз");
    }
    const code = params.get("code");
    if (!code || !verifier) {
      throw new ApiError(0, "OAUTH_MISSING_CODE", "Microsoft не повернув код входу");
    }
    const auth = await request<AuthResponse>("/auth/microsoft", {
      method: "POST",
      auth: false,
      body: { code, code_verifier: verifier, redirect_uri: `${window.location.origin}/auth/callback` },
    });
    setAccessToken(auth.access_token);
    return auth;
  } finally {
    sessionStorage.removeItem(VERIFIER_KEY);
    sessionStorage.removeItem(STATE_KEY);
  }
}
