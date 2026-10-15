// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: handlers.test.ts.
import type { Me } from "../api/types";
import { emptyMe } from "./fixtures";

/** Стан моків у пам'яті; у тестах скидається після кожного тесту. */
export const db: { signedIn: boolean; me: Me } = { signedIn: false, me: emptyMe() };

export function resetMockDb(): void {
  db.signedIn = false;
  db.me = emptyMe();
}
