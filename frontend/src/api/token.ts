// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: client.test.ts.
// Access-токен живе лише в пам'яті модуля: ніколи не пишемо його в localStorage чи cookie (R7).
let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}
