// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: catalog.test.tsx.
import { useMemo, useState } from "react";
import { ApiError } from "../../api/errors";
import type { Discipline } from "../../api/types";
import { creditsWord, formatCredits } from "../../lib/credits";
import { trimesterLabel, type Trimester } from "../../lib/trimester";
import { Segmented } from "../../ui/Segmented";
import { Pagination } from "../catalog/Pagination";
import { PAGE_SIZE, type DisciplineFilters } from "../catalog/filters";
import { useDebouncedValue } from "../catalog/useDebouncedValue";
import { useDirections, useDisciplines } from "../catalog/useDisciplines";
import { DraggableRow } from "./dnd";
import { isFreeElective, type BuilderPlan } from "./plan";

const TRIMESTERS = [
  { value: 0, label: "Усі" },
  { value: 1, label: "Осінь" },
  { value: 2, label: "Весна" },
  { value: 3, label: "Літо" },
];

const fieldClass =
  "w-full rounded-[10px] border border-rule bg-paper px-3 py-2 text-sm text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt";

export type RowState = "available" | "in-plan" | "normative" | "taken";

const REASON: Record<Exclude<RowState, "available">, string> = {
  "in-plan": "Вже в плані",
  normative: "Додав деканат",
  taken: "Вже пройдено",
};

export function CatalogRow({
  discipline,
  state,
  free,
  onAdd,
}: {
  discipline: Discipline;
  state: RowState;
  free: boolean;
  onAdd: (discipline: Discipline) => void;
}) {
  const disabled = state !== "available";
  return (
    <div className={"grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 rounded-[10px] bg-paper px-3 py-2.5 " + (disabled ? "opacity-60" : "")}>
      <div className="min-w-0">
        <b className="break-words font-semibold">{discipline.title}</b>
        <small className="block break-words text-ink-2">
          {discipline.instructor} · {trimesterLabel(discipline.trimester as Trimester)} ·{" "}
          {formatCredits(discipline.credits)} {creditsWord(discipline.credits)}
        </small>
        <div className="mt-1 flex flex-wrap gap-1.5 text-[11px]">
          {free ? (
            <span className="rounded-full px-2 py-px text-violet-text ring-1 ring-inset ring-violet">вільний вибір</span>
          ) : (
            <span className="rounded-full px-2 py-px text-cobalt ring-1 ring-inset ring-cobalt">профорієнтовна</span>
          )}
          {disabled && <span className="text-ink-2">{REASON[state]}</span>}
        </div>
      </div>
      <button
        type="button"
        aria-label={`Додати ${discipline.title}`}
        disabled={disabled}
        onClick={() => onAdd(discipline)}
        className="size-9 cursor-pointer rounded-[10px] bg-cobalt text-lg text-on-accent transition-transform duration-150 ease-out active:scale-[.94] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt disabled:cursor-not-allowed disabled:bg-rule disabled:text-ink-2"
      >
        +
      </button>
    </div>
  );
}

export function CatalogPanel({
  plan,
  studentDirections,
  normativeIds,
  takenIds,
  onAdd,
  draggable = false,
}: {
  plan: BuilderPlan;
  studentDirections: string[];
  normativeIds: number[];
  takenIds: number[];
  onAdd: (discipline: Discipline) => void;
  /** Малює ручку перетягування; потребує BuilderDnd вище по дереву. */
  draggable?: boolean;
}) {
  const [trimester, setTrimester] = useState(0);
  const [direction, setDirection] = useState("");
  const [instructor, setInstructor] = useState("");
  const [page, setPage] = useState(1);
  const debouncedInstructor = useDebouncedValue(instructor, 300);

  const filters: DisciplineFilters = useMemo(
    () => ({
      ...(trimester ? { trimester: trimester as 1 | 2 | 3 } : {}),
      ...(direction ? { direction } : {}),
      ...(debouncedInstructor.trim() ? { instructor: debouncedInstructor.trim() } : {}),
    }),
    [trimester, direction, debouncedInstructor],
  );
  const query = useDisciplines(filters, page);
  const directions = useDirections().data?.directions ?? [];
  const items = query.data?.disciplines ?? [];

  function stateOf(discipline: Discipline): RowState {
    if (plan.items.some((item) => item.course_id === discipline.id)) return "in-plan";
    if (normativeIds.includes(discipline.id)) return "normative";
    if (takenIds.includes(discipline.id)) return "taken";
    return "available";
  }

  let list;
  if (query.isPending) {
    list = (
      <div aria-label="Завантажуємо каталог" aria-busy="true" className="grid gap-2">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="h-16 animate-pulse rounded-[10px] bg-rule" />
        ))}
      </div>
    );
  } else if (query.isError) {
    list = (
      <p role="alert" className="rounded-[10px] bg-bad-bg px-4 py-3 text-bad">
        {query.error instanceof ApiError ? query.error.message : "Не вдалося завантажити каталог"}
      </p>
    );
  } else if (items.length === 0) {
    list = <p className="py-6 text-center text-ink-2">Нічого не знайдено</p>;
  } else {
    list = (
      <div className="grid gap-2">
        {items.map((discipline) => {
          const state = stateOf(discipline);
          const row = (
            <CatalogRow
              discipline={discipline}
              state={state}
              free={isFreeElective(discipline, studentDirections)}
              onAdd={onAdd}
            />
          );
          return draggable ? (
            <DraggableRow key={discipline.id} discipline={discipline} disabled={state !== "available"}>
              {row}
            </DraggableRow>
          ) : (
            <div key={discipline.id}>{row}</div>
          );
        })}
      </div>
    );
  }

  return (
    <aside aria-label="Каталог вибіркових" className="grid content-start gap-3 rounded-2xl border border-rule bg-surface p-4">
      <h2 className="font-display text-[15px]">Каталог вибіркових</h2>
      <Segmented
        value={trimester}
        options={TRIMESTERS}
        ariaLabel="Триместр"
        onChange={(value) => {
          setTrimester(value);
          setPage(1);
        }}
      />
      <div className="grid gap-1.5">
        <label htmlFor="b-direction" className="text-sm font-semibold">
          Напрямок
        </label>
        <select
          id="b-direction"
          className={fieldClass}
          value={direction}
          onChange={(event) => {
            setDirection(event.target.value);
            setPage(1);
          }}
        >
          <option value="">Усі напрямки</option>
          {directions.map((item) => (
            <option key={item.id} value={item.name}>
              {item.name}
            </option>
          ))}
        </select>
      </div>
      <div className="grid gap-1.5">
        <label htmlFor="b-instructor" className="text-sm font-semibold">
          Викладач
        </label>
        <input
          id="b-instructor"
          className={fieldClass}
          placeholder="Прізвище"
          value={instructor}
          onChange={(event) => {
            setInstructor(event.target.value);
            setPage(1);
          }}
        />
      </div>
      <div className="max-h-[520px] overflow-auto">{list}</div>
      <Pagination page={page} pageSize={PAGE_SIZE} total={query.data?.pagination.total ?? 0} onPage={setPage} />
    </aside>
  );
}
