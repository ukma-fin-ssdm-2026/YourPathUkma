// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test.
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
