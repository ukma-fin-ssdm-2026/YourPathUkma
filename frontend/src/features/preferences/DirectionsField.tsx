// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: form.test.tsx.
import type { Direction } from "../../api/types";
import { MAX_DIRECTIONS } from "./preferences";

export function DirectionsField({
  directions,
  value,
  onToggle,
  error,
}: {
  directions: Direction[];
  value: number[];
  onToggle: (id: number) => void;
  error?: string;
}) {
  const full = value.length >= MAX_DIRECTIONS;
  return (
    <section aria-labelledby="directions-title" className="grid gap-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="directions-title" className="font-display text-base">
          Напрямки розвитку
        </h2>
        <span className="font-display text-sm text-ink-2">
          {value.length} / {MAX_DIRECTIONS}
        </span>
      </div>
      <p className="text-ink-2">Оберіть до трьох. Ми підберемо дисципліни під них.</p>
      <div className="flex flex-wrap gap-2">
        {directions.map((direction) => {
          const selected = value.includes(direction.id);
          return (
            <button
              key={direction.id}
              type="button"
              aria-pressed={selected}
              disabled={full && !selected}
              onClick={() => onToggle(direction.id)}
              className={
                "cursor-pointer rounded-full border px-4 py-1.5 font-medium transition-[transform,background-color] duration-150 ease-out active:scale-[.97] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt disabled:cursor-not-allowed disabled:opacity-45 " +
                (selected ? "border-cobalt bg-cobalt text-on-accent" : "border-rule text-ink")
              }
            >
              {direction.name}
            </button>
          );
        })}
      </div>
      {error && (
        <p role="alert" className="text-sm text-bad">
          {error}
        </p>
      )}
    </section>
  );
}
