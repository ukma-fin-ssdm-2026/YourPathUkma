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
  const activeIndex = options.findIndex((option) => option.value === value);
  return (
    <div role="group" aria-label={ariaLabel} className="relative flex rounded-[10px] bg-paper p-[3px]">
      {activeIndex >= 0 && (
        <span
          aria-hidden="true"
          className="absolute inset-y-[3px] left-[3px] rounded-lg bg-surface shadow-sm transition-transform duration-300 ease-[var(--ease-out)]"
          style={{ width: `calc((100% - 6px) / ${options.length})`, transform: `translateX(${activeIndex * 100}%)` }}
        />
      )}
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
              "relative z-10 flex-1 cursor-pointer rounded-lg px-1.5 py-2 font-medium transition-colors duration-150 ease-out active:scale-[.97] " +
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt " +
              "disabled:cursor-not-allowed disabled:opacity-60 " +
              (active ? "text-ink" : "text-ink-2 hover:text-ink")
            }
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
