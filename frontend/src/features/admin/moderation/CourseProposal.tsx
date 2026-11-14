// Використання ШІ: Codex створив картку пропозиції САЗ. Перевірка: moderation.test.tsx, lint, build.
import type { ReactNode } from "react";
import { Badge } from "../../../ui/Badge";

const TRIMESTERS = new Map([
  ["1", "Осінь"],
  ["2", "Весна"],
  ["3", "Літо"],
]);
const KINDS = new Map([
  ["elective", "Вибіркова"],
  ["normative", "Нормативна"],
]);

function display(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (typeof value === "number") return value.toLocaleString("uk-UA", { useGrouping: false });
  return "";
}

function rows(value: unknown, format: (row: Record<string, unknown>) => string): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((row): row is Record<string, unknown> => !!row && typeof row === "object")
    .map(format)
    .filter(Boolean);
}

function Field({
  label,
  children,
  className = "",
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`min-w-0 ${className}`}>
      <dt className="text-xs font-medium text-ink-2">{label}</dt>
      <dd className="mt-0.5 wrap-anywhere">{children}</dd>
    </div>
  );
}

function FieldList({ values }: { values: string[] }) {
  return (
    <ul className="space-y-1">
      {values.map((value, index) => (
        <li key={`${index}-${value}`}>{value}</li>
      ))}
    </ul>
  );
}

export function CourseProposal({ payload }: { payload: Record<string, unknown> }) {
  const kind = display(payload.kind);
  const trimester = display(payload.trimester);
  const description = display(payload.description);
  const instructors = Array.isArray(payload.instructors)
    ? payload.instructors.map(display).filter(Boolean)
    : [];
  const semesters = rows(payload.semesters, (row) => {
    const number = display(row.number);
    const credits = display(row.credits);
    return [number && `${number} семестр`, display(row.season), credits && `${credits} кред.`]
      .filter(Boolean)
      .join(" · ");
  });
  const specialties = rows(payload.specialties, (row) =>
    [display(row.name), display(row.type)].filter(Boolean).join(" · "),
  );

  const summary = Object.entries({
    "Кредити ЄКТС": display(payload.credits),
    Триместр: TRIMESTERS.get(trimester) ?? trimester,
    "Рекомендований курс": display(payload.recommended_year),
    "Код САЗ": display(payload.saz_code),
  }).filter(([, value]) => value);
  const details = Object.entries({
    Факультет: display(payload.faculty),
    Кафедра: display(payload.department),
    "Рівень освіти": display(payload.level),
    "Навчальний рік": display(payload.academic_year),
    "Внутрішній ID САЗ": display(payload.saz_internal_id),
  }).filter(([, value]) => value);
  const hasDetails =
    !!description ||
    details.length > 0 ||
    semesters.length > 0 ||
    specialties.length > 0 ||
    Array.isArray(payload.instructors);

  return (
    <div className="mt-3 space-y-3 text-sm">
      {(kind || payload.happened === false) && (
        <div className="flex flex-wrap gap-2">
          {kind && <Badge tone="neutral">{KINDS.get(kind) ?? kind}</Badge>}
          {payload.happened === false && <Badge tone="warn">Курс не відбувся</Badge>}
        </div>
      )}
      {summary.length > 0 && (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-xl bg-paper p-3 lg:grid-cols-4">
          {summary.map(([label, value]) => (
            <Field key={label} label={label}>
              {value}
            </Field>
          ))}
        </dl>
      )}
      {hasDetails && (
        <details className="rounded-xl border border-rule px-3">
          <summary className="cursor-pointer py-2 font-medium text-cobalt">
            Деталі дисципліни
          </summary>
          <dl className="grid gap-x-4 gap-y-3 border-t border-rule py-3 sm:grid-cols-2">
            {description && (
              <Field label="Опис" className="sm:col-span-2">
                <p className="whitespace-pre-line">{description}</p>
              </Field>
            )}
            {semesters.length > 0 && (
              <Field label="Семестри">
                <FieldList values={semesters} />
              </Field>
            )}
            {specialties.length > 0 && (
              <Field label="Спеціальності">
                <FieldList values={specialties} />
              </Field>
            )}
            {Array.isArray(payload.instructors) && (
              <Field label="Викладачі">
                {instructors.length ? <FieldList values={instructors} /> : "Не вказано"}
              </Field>
            )}
            {details.map(([label, value]) => (
              <Field key={label} label={label}>
                {value}
              </Field>
            ))}
          </dl>
        </details>
      )}
    </div>
  );
}
