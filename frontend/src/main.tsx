// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm run build, ручний запуск dev.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./styles/index.css";
import { App } from "./App";

const queryClient = new QueryClient();

/** Моки лише для ендпоінтів, яких немає в бекенді; решта запитів іде на реальний сервер. */
async function enableMocks(): Promise<void> {
  if (import.meta.env.VITE_USE_MOCKS !== "true") return;
  const { worker } = await import("./mocks/browser");
  await worker.start({ onUnhandledRequest: "bypass" });
}

void enableMocks().then(() => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </StrictMode>,
  );
});
