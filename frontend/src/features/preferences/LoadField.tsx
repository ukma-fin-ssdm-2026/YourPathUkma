// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: form.test.tsx.
import type { LoadLevel, LoadLevels } from "../../api/types";
import { Segmented } from "../../ui/Segmented";

const SEASONS = [
  { key: "autumn", label: "Осінь", name: "осінь", locative: "Восени", dot: "bg-autumn" },
  { key: "spring", label: "Весна", name: "весна", locative: "Навесні", dot: "bg-spring" },
  { key: "summer", label: "Літо", name: "літо", locative: "Влітку", dot: "bg-summer" },
] as const;

const OPTIONS: { value: LoadLevel; label: string }[] = [
  { value: "low", label: "Низьке" },
  { value: "medium", label: "Середнє" },
  { value: "high", label: "Високе" },
];

export function LoadField({
  value,
  onChange,
  locked,
  hint,
}: {
  value: LoadLevels;
  onChange: (season: "autumn" | "spring" | "summer", level: LoadLevel) => void;
  locked: boolean;
  hint?: string;
}) {
  return (
    <section aria-labelledby="load-title" className="grid gap-3">
      <h2 id="load-title" className="font-display text-base">
        Навантаження по триместрах
      </h2>
      {hint && <p className="text-ink-2">{hint}</p>}
      {locked && (
        <p className="rounded-[10px] bg-info-bg px-4 py-2.5 text-sm">
          Для 4 курсу навантаження розраховується автоматично.
        </p>
      )}
      <div className="grid grid-cols-[90px_1fr] items-center gap-x-4 gap-y-2">
        {SEASONS.map((season) => (
          <div key={season.key} className="contents">
            <span className="flex items-center gap-2 font-semibold">
              <i aria-hidden="true" className={`block size-2.5 rounded-full ${season.dot}`} />
              {season.label}
            </span>
            <Segmented
              value={value[season.key] ?? "medium"}
              options={OPTIONS}
              ariaLabel={`Навантаження: ${season.name}`}
              disabled={locked}
              onChange={(level) => onChange(season.key, level)}
            />
          </div>
        ))}
      </div>
      {SEASONS.filter((season) => value[season.key] === "low").map((season) => (
        <p key={season.key} className="rounded-[10px] bg-warn-bg px-4 py-2.5 text-sm text-warn">
          {season.locative} обрано низьке навантаження: щоб набрати 57–60 кредитів за рік,
          навантаження наступних років зросте.
        </p>
      ))}
    </section>
  );
}
