// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: users.test.tsx.
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "../../../api/client";
import type { ApiError } from "../../../api/errors";
import type { AdminUser, AdminUserPatch, PaginationInfo, UserRole } from "../../../api/types";

export const USERS_PAGE_SIZE = 20;

type CourseYearSource = NonNullable<NonNullable<AdminUser["student"]>["course_year_source"]>;

const SOURCE_LABEL: Record<CourseYearSource, string> = {
  self_declared: "Вказав студент",
  admin: "Адмін",
  saz_sync: "Синхронізація САЗ",
};

export const courseYearSourceLabel = (source: CourseYearSource | null) =>
  source ? SOURCE_LABEL[source] : "—";

export function useAdminUsers({ q, role, page }: { q: string; role?: UserRole; page: number }) {
  return useQuery({
    queryKey: ["admin", "users", q, role ?? "all", page],
    placeholderData: keepPreviousData,
    queryFn: () =>
      request<{ users: AdminUser[]; pagination: PaginationInfo }>("/admin/users", {
        query: {
          limit: USERS_PAGE_SIZE,
          offset: (page - 1) * USERS_PAGE_SIZE,
          q: q || undefined,
          role,
        },
      }),
  });
}

export function usePatchUser() {
  const queryClient = useQueryClient();
  return useMutation<AdminUser, ApiError, { id: number; patch: AdminUserPatch }>({
    mutationFn: ({ id, patch }) =>
      request<AdminUser>(`/admin/users/${id}`, { method: "PATCH", body: patch }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
}
