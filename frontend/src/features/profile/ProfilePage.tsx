// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: profile.test.tsx.
import type { CSSProperties } from "react";
import { Link } from "react-router";
import { useConfig } from "../../api/config";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { linkButtonClass } from "../../ui/linkButton";
import { CreditsLedger } from "./CreditsLedger";
import { LimitsStrip } from "./LimitsStrip";
import { useAcademicHistory, useMe } from "./useMe";

/** Рік плану за замовчуванням: поточний календарний, у межах навчальних років з /config. */
export function defaultPlanYear(now: Date, min: number, max: number): number {
  return Math.min(max, Math.max(min, now.getFullYear()));
}

export function ProfilePage() {
  const me = useMe();
  const history = useAcademicHistory();
  const config = useConfig();
  const student = me.data?.student;

  if (me.isError) {
    return (
      <p role="alert" className="text-bad">
        Не вдалося завантажити профіль. Оновіть сторінку.
      </p>
    );
  }
  if (!me.data) {
    return (
      <p role="status" className="text-ink-2">
        Завантаження…
      </p>
    );
  }
  if (!student) {
    return <p className="text-ink-2">Для облікового запису адміністратора профіль студента не потрібен.</p>;
  }

  const limits = config.data?.limits;
  const year = defaultPlanYear(new Date(), limits?.academic_year_min ?? 2024, limits?.academic_year_max ?? 2030);

  return (
    <div className="grid gap-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-[28px] leading-tight">
            Ваш шлях до {student.credits.total_limit} кредитів
          </h1>
          <p className="mt-1.5 text-ink-2">
            {student.course_year} курс · {student.specialty}
          </p>
        </div>
        <div className="grid justify-items-end gap-1">
          {student.can_create_plan ? (
            <Link to="/path/create" className={linkButtonClass}>
              Створити план на {year}
            </Link>
          ) : (
            <>
              <Button disabled>Створити план на {year}</Button>
              {student.course_year === 1 && (
                <small className="text-sm text-ink-2">Для 1 курсу план формує деканат.</small>
              )}
            </>
          )}
        </div>
      </div>

      <Card className="rise p-7" style={{ "--i": 1 } as CSSProperties}>
        <div className="mb-5 flex flex-wrap items-baseline justify-between gap-3">
          <h2 className="font-display text-base">Кредити за чотири роки</h2>
        </div>
        <LimitsStrip credits={student.credits} />
        <div className="mt-7">
          {history.isPending ? (
            <div role="status" aria-label="Завантажуємо журнал кредитів" className="h-40 shimmer rounded-xl bg-rule" />
          ) : history.isError ? (
            <p role="alert" className="text-bad">
              Не вдалося завантажити історію навчання.
            </p>
          ) : (
            <CreditsLedger years={history.data.years} />
          )}
        </div>
      </Card>
    </div>
  );
}
