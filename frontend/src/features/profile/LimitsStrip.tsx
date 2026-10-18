// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: profile.test.tsx.
import type { Credits } from "../../api/types";
import { creditsPercent, formatCredits } from "../../lib/credits";
import { CountUp } from "../../ui/CountUp";

function Limit({
  label,
  used,
  limit,
  barClass,
}: {
  label: string;
  used: number;
  limit: number;
  barClass: string;
}) {
  const percent = creditsPercent(used, limit);
  return (
    <div className="p-1">
      <div className="text-sm text-ink-2">{label}</div>
      <div className="font-display text-2xl">
        <CountUp value={used} /> <small className="font-sans text-sm text-ink-2">з {formatCredits(limit)}</small>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-rule">
        <div
          role="progressbar"
          aria-label={label}
          aria-valuemin={0}
          aria-valuemax={limit}
          aria-valuenow={used}
          className={`bar-grow h-full rounded-full ${barClass}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

export function LimitsStrip({ credits }: { credits: Credits }) {
  return (
    <div className="grid gap-6 sm:grid-cols-3">
      <Limit label="Усього" used={credits.total_used} limit={credits.total_limit} barClass="bg-ink" />
      <Limit
        label="Профорієнтовні"
        used={credits.professional_used}
        limit={credits.professional_limit}
        barClass="bg-cobalt"
      />
      <Limit
        label="Вільний вибір"
        used={credits.free_choice_used}
        limit={credits.free_choice_limit}
        barClass="bg-violet"
      />
    </div>
  );
}
