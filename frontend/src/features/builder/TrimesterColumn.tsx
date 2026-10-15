// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: columns.test.tsx.
import type { LoadLevel, NormativeCourse, PlanItem } from "../../api/types";
import { formatCredits } from "../../lib/credits";
import { trimesterLabel, type Trimester } from "../../lib/trimester";
import { Segmented } from "../../ui/Segmented";
import { PlanItemCard } from "./PlanItemCard";

const LOAD_OPTIONS: { value: LoadLevel; label: string }[] = [
  { value: "low", label: "Низьке" },
  { value: "medium", label: "Середнє" },
  { value: "high", label: "Високе" },
];

const ACCENT: Record<Trimester, string> = {
  1: "border-t-autumn",
  2: "border-t-spring",
  3: "border-t-summer",
};

/** Дисципліна, яку додав деканат: лише для читання. */
export function NormativeCard({ course }: { course: NormativeCourse }) {
  return (
    <div className="flex items-start justify-between gap-2 rounded-[10px] bg-[repeating-linear-gradient(135deg,transparent_0_6px,rgba(120,130,170,.14)_6px_7px)] px-3 py-2.5 text-ink-2 ring-1 ring-inset ring-rule">
      <div>
        <span className="break-words">{course.raw_title}</span>
        <small className="block text-xs">від деканату</small>
      </div>
      <b className="font-display text-sm">{formatCredits(course.credits)}</b>
    </div>
  );
}

export function TrimesterColumn({
  trimester,
  items,
  normative,
  load,
  loadLocked,
  onLoadChange,
  onRemove,
  itemErrors = {},
  dropHint = null,
}: {
  trimester: Trimester;
  items: PlanItem[];
  normative: NormativeCourse[];
  load: LoadLevel;
  loadLocked: boolean;
  onLoadChange: (level: LoadLevel) => void;
  onRemove: (courseId: number) => void;
  itemErrors?: Record<number, string>;
  dropHint?: string | null;
}) {
  const label = trimesterLabel(trimester);
  const total =
    items.reduce((sum, item) => sum + item.credits, 0) +
    normative.reduce((sum, course) => sum + course.credits, 0);
  return (
    <section
      aria-label={label}
      data-trimester={trimester}
      className={`grid content-start gap-2 rounded-2xl border border-t-4 border-rule bg-surface p-3 ${ACCENT[trimester]}`}
    >
      <div className="flex items-baseline justify-between">
        <h2 className="font-display text-[15px]">{label}</h2>
        <span className="text-[13px] text-ink-2">{formatCredits(total)} кр.</span>
      </div>
      <Segmented
        value={load}
        options={LOAD_OPTIONS}
        ariaLabel={`Навантаження: ${label.toLowerCase()}`}
        disabled={loadLocked}
        onChange={onLoadChange}
      />
      {items.map((item) => (
        <PlanItemCard key={item.course_id} item={item} error={itemErrors[item.course_id]} onRemove={onRemove} />
      ))}
      {normative.map((course) => (
        <NormativeCard key={`${course.raw_title}-${course.trimester}`} course={course} />
      ))}
      {dropHint ? (
        <p role="status" className="rounded-[10px] border-[1.5px] border-dashed border-bad px-3 py-3.5 text-center text-[13px] text-bad">
          {dropHint}
        </p>
      ) : (
        <p className="rounded-[10px] border-[1.5px] border-dashed border-rule px-3 py-3.5 text-center text-[13px] text-ink-2">
          Перетягніть дисципліну сюди
        </p>
      )}
    </section>
  );
}
