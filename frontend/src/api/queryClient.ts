// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: session.test.ts.
import { QueryClient } from "@tanstack/react-query";

/** Єдиний клієнт запитів застосунку; сесія очищає його при виході, щоб дані не переходили між користувачами. */
export const queryClient = new QueryClient();
