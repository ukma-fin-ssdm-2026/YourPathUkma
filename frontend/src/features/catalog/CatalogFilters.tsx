// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: catalog-ui.test.tsx.
import type { Direction } from "../../api/types";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { Segmented } from "../../ui/Segmented";
import type { DisciplineFilters } from "./filters";

const fieldClass =
  "w-full rounded-[10px] border border-rule bg-paper px-3 py-2 text-sm text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt";

const TRIMESTERS = [
  { value: 0, label: "Усі" },
  { value: 1, label: "Осінь" },
  { value: 2, label: "Весна" },
  { value: 3, label: "Літо" },
];
const YEARS = [
  { value: 0, label: "Усі" },
  { value: 2, label: "2" },
  { value: 3, label: "3" },
  { value: 4, label: "4" },
];

function toNumber(raw: string): number | undefined {
  if (raw.trim() === "") return undefined;
  const value = Number(raw);
  return Number.isFinite(value) && value >= 0 ? value : undefined;
}

export function CatalogFilters({
  filters,
  directions,
  instructor,
  onInstructorChange,
  onChange,
  onReset,
}: {
  filters: DisciplineFilters;
  directions: Direction[];
  instructor: string;
  onInstructorChange: (value: string) => void;
  onChange: (next: DisciplineFilters) => void;
  onReset: () => void;
}) {
  return (
    <Card className="grid gap-4">
      <div className="grid gap-1.5">
        <label htmlFor="f-direction" className="text-sm font-semibold">
          Напрямок
        </label>
        <select
          id="f-direction"
          className={fieldClass}
          value={filters.direction ?? ""}
          onChange={(event) => onChange({ ...filters, direction: event.target.value || undefined })}
        >
          <option value="">Усі напрямки</option>
          {directions.map((direction) => (
            <option key={direction.id} value={direction.name}>
              {direction.name}
            </option>
          ))}
        </select>
      </div>

      <div className="grid gap-1.5">
        <span className="text-sm font-semibold">Триместр</span>
        <Segmented
          value={filters.trimester ?? 0}
          options={TRIMESTERS}
          ariaLabel="Триместр"
          onChange={(value) =>
            onChange({ ...filters, trimester: value === 0 ? undefined : (value as 1 | 2 | 3) })
          }
        />
      </div>

      <div className="grid gap-1.5">
        <span className="text-sm font-semibold">Кредити</span>
        <div className="grid grid-cols-2 gap-2">
          <input
            type="number"
            min={0}
            inputMode="decimal"
            className={fieldClass}
            placeholder="від"
            aria-label="Кредити від"
            value={filters.min_credits ?? ""}
            onChange={(event) => onChange({ ...filters, min_credits: toNumber(event.target.value) })}
          />
          <input
            type="number"
            min={0}
            inputMode="decimal"
            className={fieldClass}
            placeholder="до"
            aria-label="Кредити до"
            value={filters.max_credits ?? ""}
            onChange={(event) => onChange({ ...filters, max_credits: toNumber(event.target.value) })}
          />
        </div>
        {filters.min_credits !== undefined &&
          filters.max_credits !== undefined &&
          filters.min_credits > filters.max_credits && (
            <small role="alert" className="text-sm text-bad">
              «Від» не може бути більшим за «до»
            </small>
          )}
      </div>

      <div className="grid gap-1.5">
        <span className="text-sm font-semibold">Рекомендований курс</span>
        <Segmented
          value={filters.recommended_year ?? 0}
          options={YEARS}
          ariaLabel="Рекомендований курс"
          onChange={(value) =>
            onChange({ ...filters, recommended_year: value === 0 ? undefined : (value as 2 | 3 | 4) })
          }
        />
      </div>

      <div className="grid gap-1.5">
        <label htmlFor="f-instructor" className="text-sm font-semibold">
          Викладач
        </label>
        <input
          id="f-instructor"
          className={fieldClass}
          placeholder="Прізвище"
          value={instructor}
          onChange={(event) => onInstructorChange(event.target.value)}
        />
      </div>

      <Button variant="ghost" size="sm" onClick={onReset}>
        Скинути фільтри
      </Button>
    </Card>
  );
}
