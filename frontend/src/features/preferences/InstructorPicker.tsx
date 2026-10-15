// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: instructors.test.tsx.
import { useState } from "react";
import type { Instructor } from "../../api/types";
import { useDebouncedValue } from "../catalog/useDebouncedValue";
import { useInstructors } from "./usePreferences";

export function InstructorPicker({
  title,
  searchLabel,
  selectedIds,
  otherIds,
  names,
  onAdd,
  onRemove,
}: {
  title: string;
  searchLabel: string;
  selectedIds: number[];
  otherIds: number[];
  names: Map<number, string>;
  onAdd: (instructor: Instructor) => void;
  onRemove: (id: number) => void;
}) {
  const [text, setText] = useState("");
  const term = useDebouncedValue(text, 300);
  const found = useInstructors(term).data?.instructors ?? [];
  // Викладач не може бути і в цьому списку, і в протилежному, тож таких не пропонуємо.
  const options = found.filter((item) => !selectedIds.includes(item.id) && !otherIds.includes(item.id));

  return (
    <section aria-label={title} className="grid content-start gap-2">
      <h3 className="font-display text-sm">{title}</h3>
      <input
        type="search"
        aria-label={searchLabel}
        placeholder="Знайти викладача"
        value={text}
        onChange={(event) => setText(event.target.value)}
        className="w-full rounded-[10px] border border-rule bg-paper px-3 py-2 text-sm text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt"
      />
      {term.trim().length >= 2 && options.length > 0 && (
        <ul className="grid gap-1 rounded-[10px] border border-rule bg-surface p-1.5">
          {options.map((item) => (
            <li key={item.id} className="flex items-center justify-between gap-2 px-2 py-1">
              <span className="break-words">{item.full_name}</span>
              <button
                type="button"
                aria-label={`Додати ${item.full_name}`}
                onClick={() => onAdd(item)}
                className="cursor-pointer rounded-lg px-3 py-1 text-[13px] font-semibold text-cobalt ring-1 ring-inset ring-cobalt transition-transform duration-150 ease-out active:scale-[.97] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt"
              >
                Додати
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap gap-1.5">
        {selectedIds.map((id) => {
          const name = names.get(id) ?? `Викладач #${id}`;
          return (
            <span key={id} className="inline-flex items-center gap-1.5 rounded-full bg-paper px-2.5 py-1 text-[13px]">
              {name}
              <button
                type="button"
                aria-label={`Прибрати ${name}`}
                onClick={() => onRemove(id)}
                className="cursor-pointer px-0.5 text-ink-2 focus-visible:outline-2 focus-visible:outline-cobalt"
              >
                ✕
              </button>
            </span>
          );
        })}
      </div>
    </section>
  );
}
