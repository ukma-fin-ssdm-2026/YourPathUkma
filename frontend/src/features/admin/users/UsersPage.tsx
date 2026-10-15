// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: users.test.tsx.
import { useState } from "react";
import type { AdminUser, UserRole } from "../../../api/types";
import { formatDateTime } from "../../../lib/datetime";
import { Button } from "../../../ui/Button";
import { Segmented } from "../../../ui/Segmented";
import { Pagination } from "../../catalog/Pagination";
import { useDebouncedValue } from "../../catalog/useDebouncedValue";
import { UserEditor } from "./UserEditor";
import { USERS_PAGE_SIZE, courseYearSourceLabel, useAdminUsers } from "./useUsers";

const ROLE_FILTER: { value: UserRole | "all"; label: string }[] = [
  { value: "all", label: "Усі" },
  { value: "student", label: "Студенти" },
  { value: "admin", label: "Адміни" },
];

const CELL = "px-3 py-2 text-left align-top";

export function UsersPage() {
  const [search, setSearch] = useState("");
  const [role, setRole] = useState<UserRole | "all">("all");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<AdminUser | null>(null);
  const q = useDebouncedValue(search.trim(), 250);
  const users = useAdminUsers({ q, role: role === "all" ? undefined : role, page });
  const list = users.data?.users ?? [];

  return (
    <section aria-label="Користувачі">
      <h1 className="font-display text-[22px]">Користувачі</h1>
      <div className="mt-4 flex flex-wrap items-end gap-3">
        <label className="flex min-w-[240px] flex-1 flex-col gap-1 font-medium">
          Пошук за поштою або ім'ям
          <input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            className="rounded-[10px] border border-rule bg-surface px-3 py-2 font-normal"
          />
        </label>
        <Segmented
          ariaLabel="Роль"
          value={role}
          options={ROLE_FILTER}
          onChange={(value) => {
            setRole(value);
            setPage(1);
          }}
        />
      </div>

      <div className="mt-4 overflow-x-auto">
        {users.isError ? (
          <p role="alert" className="text-bad">
            Не вдалося завантажити користувачів
          </p>
        ) : users.isSuccess && list.length === 0 ? (
          <p className="text-ink-2">Користувачів не знайдено</p>
        ) : (
          <table className="w-full min-w-[720px] border-collapse">
            <thead>
              <tr className="border-b border-rule text-ink-2">
                <th className={CELL}>Користувач</th>
                <th className={CELL}>Роль</th>
                <th className={CELL}>Курс</th>
                <th className={CELL}>Спеціальність</th>
                <th className={CELL}>Джерело курсу</th>
                <th className={CELL}>Остання активність</th>
                <th className={CELL}>
                  <span className="sr-only">Дії</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {list.map((user) => (
                <tr key={user.id} className="border-b border-rule">
                  <td className={`${CELL} break-words`}>
                    <div className="font-medium">{user.full_name}</div>
                    <div className="text-ink-2">{user.email}</div>
                  </td>
                  <td className={CELL}>{user.role === "admin" ? "Адмін" : "Студент"}</td>
                  <td className={CELL}>{user.student?.course_year ?? "—"}</td>
                  <td className={`${CELL} break-words`}>{user.student?.specialty ?? "—"}</td>
                  <td className={CELL}>{courseYearSourceLabel(user.student?.course_year_source ?? null)}</td>
                  <td className={CELL}>{formatDateTime(user.last_login_at)}</td>
                  <td className={CELL}>
                    <Button variant="ghost" size="sm" onClick={() => setEditing(user)}>
                      Змінити
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {users.data && (
        <Pagination page={page} pageSize={USERS_PAGE_SIZE} total={users.data.pagination.total} onPage={setPage} />
      )}
      {editing && <UserEditor key={editing.id} user={editing} onClose={() => setEditing(null)} />}
    </section>
  );
}
