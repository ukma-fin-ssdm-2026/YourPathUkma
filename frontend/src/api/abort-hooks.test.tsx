// Використання ШІ: Codex додав перевірку скасування query-запитів #220; Vitest.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { useSession } from "../auth/session";
import { setFetch } from "./client";
import { useDisciplines } from "../features/catalog/useDisciplines";
import { useDeaneryDocuments, useDeaneryDocument } from "../features/deanery/useDeanery";
import { useAdminUsers } from "../features/admin/users/useUsers";
import { useAuditLog } from "../features/admin/audit/useAudit";
import { useModerationItems } from "../features/admin/moderation/useModeration";
import { useAcademicHistory } from "../features/profile/useMe";

it.each([
  ["catalog", () => useDisciplines({}, 0)],
  ["documents", () => useDeaneryDocuments(2026)],
  ["document", () => useDeaneryDocument(1)],
  ["users", () => useAdminUsers({ q: "", page: 0 })],
  ["audit", () => useAuditLog({ action: "", page: 0 })],
  ["moderation", () => useModerationItems({ page: 0 })],
  ["history", () => useAcademicHistory()],
] as const)("aborts %s when its consumer unmounts", async (_name, hook) => {
  useSession.setState({ status: "authenticated" });
  let signal: AbortSignal | null | undefined;
  setFetch((_url, init) => {
    signal = init?.signal;
    return new Promise((_resolve, reject) =>
      signal?.addEventListener("abort", () => reject(new DOMException("cancelled", "AbortError")), {
        once: true,
      }),
    );
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const view = renderHook(() => hook(), { wrapper });
  await waitFor(() => expect(signal).toBeDefined());
  view.unmount();
  expect(signal?.aborted).toBe(true);
  client.clear();
});
