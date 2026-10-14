// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: ui.test.tsx.
type SegmentedProps<T extends string | number> = {
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
  ariaLabel: string;
  disabled?: boolean;
};

export function Segmented<T extends string | number>({
  value,
  options,
  onChange,
  ariaLabel,
  disabled = false,
}: SegmentedProps<T>) {
  return (
    <div role="group" aria-label={ariaLabel} className="flex rounded-[10px] bg-paper p-[3px]">
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={String(option.value)}
            type="button"
            aria-pressed={active}
            disabled={disabled}
            onClick={() => onChange(option.value)}
            className={
              "flex-1 cursor-pointer rounded-lg px-1.5 py-2 font-medium transition-[background-color,color] duration-150 ease-out " +
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt " +
              "disabled:cursor-not-allowed disabled:opacity-60 " +
              (active ? "bg-surface text-ink shadow-sm" : "text-ink-2")
            }
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
