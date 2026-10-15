// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: ручний запуск dev з VITE_USE_MOCKS=true.
import { setupWorker } from "msw/browser";
import { coreHandlers } from "./core";
import { handlers } from "./handlers";

export const worker = setupWorker(
  ...(import.meta.env.VITE_USE_MOCKS === "full" ? coreHandlers : []),
  ...handlers,
);
