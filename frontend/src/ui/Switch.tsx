// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: instructors.test.tsx.
export function Switch({
  checked,
  onChange,
  label,
  description,
  badge,
  disabled = false,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  description?: string;
  badge?: string;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
      <div>
        <b className="font-semibold">{label}</b>
        {badge && (
          <span className="ml-2 rounded-full bg-paper px-2 py-px text-[11px] text-ink-2">
            {badge}
          </span>
        )}
        {description && <small className="block text-ink-2">{description}</small>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={
          "relative h-6 w-[42px] shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-out focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt disabled:cursor-not-allowed disabled:opacity-45 " +
          (checked ? "bg-cobalt" : "bg-rule")
        }
      >
        <span
          aria-hidden="true"
          className={
            "absolute top-[3px] left-[3px] size-[18px] rounded-full bg-white transition-transform duration-300 ease-[var(--ease-spring)] " +
            (checked ? "translate-x-[18px]" : "")
          }
        />
      </button>
    </div>
  );
}
