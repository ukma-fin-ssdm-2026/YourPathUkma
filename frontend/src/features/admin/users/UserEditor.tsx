// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: users.test.tsx.
import { useEffect, useState } from "react";
import { fieldErrors } from "../../../api/errors";
import type { AdminUser, AdminUserPatch, UserRole } from "../../../api/types";
import { Button } from "../../../ui/Button";
import { Segmented } from "../../../ui/Segmented";
import { usePatchUser } from "./useUsers";
import { toast } from "sonner";

const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: "student", label: "Студент" },
  { value: "admin", label: "Адмін" },
];

const INPUT = "rounded-[10px] border border-rule bg-surface px-3 py-2 font-normal";

export function UserEditor({ user, onClose }: { user: AdminUser; onClose: () => void }) {
  const [role, setRole] = useState<UserRole>(user.role);
  const [courseYear, setCourseYear] = useState(String(user.student?.course_year ?? ""));
  const [specialty, setSpecialty] = useState(user.student?.specialty ?? "");
  const [clientError, setClientError] = useState<string | null>(null);
  const patchUser = usePatchUser();

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const patch: AdminUserPatch = {};
  if (role !== user.role) patch.role = role;
  if (user.student) {
    const student: NonNullable<AdminUserPatch["student"]> = {};
    if (courseYear && Number(courseYear) !== user.student.course_year) {
      student.course_year = Number(courseYear) as 1 | 2 | 3 | 4;
    }
    if (specialty !== (user.student.specialty ?? "")) student.specialty = specialty.trim();
    if (Object.keys(student).length > 0) patch.student = student;
  }
  const changed = Object.keys(patch).length > 0;

  const save = () => {
    if (patch.student?.specialty !== undefined && (patch.student.specialty.length < 2 || patch.student.specialty.length > 150)) {
      setClientError("Від 2 до 150 символів");
      return;
    }
    setClientError(null);
    patchUser.mutate({ id: user.id, patch }, {
      onSuccess: () => {
        toast.success("Зміни збережено");
        onClose();
      },
    });
  };

  const error = patchUser.error;
  const server = error ? fieldErrors(error.details) : null;
  const specialtyError = clientError ?? server?.fields["student.specialty"];
  const formError = error
    ? error.code === "CANNOT_CHANGE_OWN_ROLE"
      ? "Не можна змінити власну роль"
      : [...(server?.form ?? []), ...(specialtyError || server?.form.length ? [] : [error.message])].join(" ")
    : null;

  return (
    <div className="fixed inset-0 z-10 grid place-items-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Змінити користувача"
        className="w-full max-w-md rounded-2xl border border-rule bg-surface p-6 shadow-xl"
      >
        <h2 className="font-display text-base">{user.full_name}</h2>
        <p className="text-ink-2">{user.email}</p>
        <div className="mt-4 flex flex-col gap-4">
          <Segmented ariaLabel="Роль" value={role} options={ROLE_OPTIONS} onChange={setRole} />
          {user.student && (
            <>
              <label className="flex flex-col gap-1 font-medium">
                Курс
                <select value={courseYear} onChange={(e) => setCourseYear(e.target.value)} className={INPUT}>
                  {!courseYear && <option value="">Не вказано</option>}
                  {[1, 2, 3, 4].map((year) => (
                    <option key={year} value={String(year)}>
                      {year}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 font-medium">
                Спеціальність
                <input value={specialty} onChange={(e) => setSpecialty(e.target.value)} className={INPUT} />
                {specialtyError && <span className="text-sm font-normal text-bad">{specialtyError}</span>}
              </label>
            </>
          )}
        </div>
        {formError && (
          <p role="alert" className="mt-4 text-bad">
            {formError}
          </p>
        )}
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Скасувати
          </Button>
          <Button disabled={!changed || patchUser.isPending} onClick={save}>
            Зберегти
          </Button>
        </div>
      </div>
    </div>
  );
}
