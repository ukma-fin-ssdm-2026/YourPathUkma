// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: columns.test.tsx.
// Codex додав пояснення та альтернативи ШІ. Перевірка: тести конструктора.
import { useEffect, useRef, useState } from "react";
import type { PlanAlternative, PlanItem } from "../../api/types";
import { formatCredits } from "../../lib/credits";
import { canAnimate } from "../../ui/motion";

export function PlanItemCard({
  item,
  error,
  onRemove,
  onAlternative,
}: {
  item: PlanItem;
  error?: string;
  onRemove: (courseId: number) => void;
  onAlternative?: (courseId: number, alternative: PlanAlternative) => void;
}) {
  const [leaving, setLeaving] = useState(false);
  const timer = useRef(0);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  /** Спершу відлітає картка, і лише потім дисципліна прибирається з плану. */
  function handleRemove() {
    if (leaving) return;
    if (!canAnimate()) return onRemove(item.course_id);
    setLeaving(true);
    timer.current = window.setTimeout(() => onRemove(item.course_id), 180);
  }

  return (
    <div
      data-testid={`item-${item.course_id}`}
      className={
        (leaving ? "leave-out " : "") +
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
          onClick={handleRemove}
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
      {item.ai_explanation && (
        <details className="border-t border-rule pt-2 text-xs">
          <summary className="cursor-pointer font-semibold text-cobalt-d">Чому запропоновано</summary>
          <p className="mt-1 wrap-break-word text-ink-2">{item.ai_explanation}</p>
        </details>
      )}
      {!!item.alternatives?.length && onAlternative && (
        <details className="border-t border-rule pt-2 text-xs">
          <summary className="cursor-pointer font-semibold text-cobalt-d">Альтернативи</summary>
          <ul className="mt-1 grid gap-2">
            {item.alternatives.map((alternative) => (
              <li key={alternative.course_id} className="grid gap-1">
                <span className="wrap-break-word">{alternative.title} · {formatCredits(alternative.credits)} кр.</span>
                <button
                  type="button"
                  className="justify-self-start rounded-md px-1 py-1 text-cobalt-d hover:underline focus-visible:outline-2"
                  aria-label={`Замінити на ${alternative.title}`}
                  onClick={() => onAlternative(item.course_id, alternative)}
                >
                  Вибрати
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
