// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: columns.test.tsx.
import type { PlanItem } from "../../api/types";
import { formatCredits } from "../../lib/credits";

export function PlanItemCard({
  item,
  error,
  onRemove,
}: {
  item: PlanItem;
  error?: string;
  onRemove: (courseId: number) => void;
}) {
  return (
    <div
      data-testid={`item-${item.course_id}`}
      className={
        "pop-in grid gap-1 rounded-[10px] bg-paper px-3 py-2.5 transition-[translate] duration-200 ease-out hover:-translate-y-0.5 " +
        (item.is_free_elective ? "shadow-[inset_3px_0_0_var(--violet)]" : "")
      }
    >
      <div className="flex items-start justify-between gap-2">
        <span className="break-words font-medium">{item.title}</span>
        <b className="font-display text-sm">{formatCredits(item.credits)}</b>
      </div>
      <div className="flex items-center justify-between gap-2 text-xs">
        {item.is_free_elective ? <span className="text-violet-text">вільний вибір</span> : <span />}
        <button
          type="button"
          aria-label={`Прибрати ${item.title}`}
          onClick={() => onRemove(item.course_id)}
          className="cursor-pointer rounded-md px-1.5 py-0.5 text-ink-2 transition-transform duration-150 ease-out hover:text-ink active:scale-[.97] focus-visible:outline-2 focus-visible:outline-cobalt"
        >
          Прибрати
        </button>
      </div>
      {error && (
        <p role="alert" className="text-xs text-bad">
          {error}
        </p>
      )}
    </div>
  );
}
