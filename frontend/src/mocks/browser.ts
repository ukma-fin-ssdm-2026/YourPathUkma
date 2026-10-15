// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: ручний запуск dev з VITE_USE_MOCKS=true.
import { setupWorker } from "msw/browser";
import { coreHandlers } from "./core";
import { backendHandlers, handlers } from "./handlers";

// `full`: усе мокається, у тому числі ендпоінти, які бекенд уже має. coreHandlers
// стоять першими, щоб їхній submit (зі станом) мав пріоритет над заглушкою.
export const worker = setupWorker(
  ...(import.meta.env.VITE_USE_MOCKS === "full" ? [...coreHandlers, ...backendHandlers] : []),
  ...handlers,
);
