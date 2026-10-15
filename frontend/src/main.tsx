// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm run build, ручний запуск dev.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import "./styles/index.css";
import { App } from "./App";
import { queryClient } from "./api/queryClient";
import { installAuth, restoreSession } from "./auth/session";

/** `true`: моки лише для ендпоінтів без бекенду. `full`: ще й каталог, плани та конфіг, бекенд не потрібен. */
async function enableMocks(): Promise<void> {
  if (!["true", "full"].includes(import.meta.env.VITE_USE_MOCKS ?? "")) return;
  const { worker } = await import("./mocks/browser");
  await worker.start({ onUnhandledRequest: "bypass" });
}

void enableMocks().then(() => {
  installAuth();
  void restoreSession();
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
        <Toaster position="bottom-right" theme="system" />
      </QueryClientProvider>
    </StrictMode>,
  );
});
