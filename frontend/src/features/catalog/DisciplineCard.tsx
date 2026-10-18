// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: catalog-ui.test.tsx.
import type { CSSProperties } from "react";
import type { Discipline } from "../../api/types";
import { creditsWord, formatCredits } from "../../lib/credits";
import { trimesterLabel, type Trimester } from "../../lib/trimester";
import { Card } from "../../ui/Card";

const tagClass = "rounded-full px-2 py-px text-[11px] ring-1 ring-inset";

export function DisciplineCard({
  discipline,
  reviewsUrl,
  index = 0,
}: {
  discipline: Discipline;
  reviewsUrl?: string;
  index?: number;
}) {
  const directions = discipline.directions ?? [];
  const trimester = trimesterLabel(discipline.trimester as Trimester);
  return (
    <Card
      className="rise flex flex-col gap-2 transition-[translate,box-shadow] duration-200 ease-out hover:-translate-y-1 hover:shadow-lg"
      style={{ "--i": Math.min(index, 8) } as CSSProperties}
    >
      <div className="flex flex-wrap gap-1.5">
        {directions.length === 0 ? (
          <span className={`${tagClass} text-violet-text ring-violet`}>вільний вибір</span>
        ) : (
          directions.slice(0, 3).map((direction) => (
            <span key={direction} className={`${tagClass} text-cobalt ring-cobalt`}>
              {direction}
            </span>
          ))
        )}
      </div>
      <h2 className="break-words font-display text-[15px] leading-snug">{discipline.title}</h2>
      <p className="break-words text-[13px] text-ink-2">
        {discipline.instructor} · {discipline.recommended_year} курс · {trimester}
      </p>
      {discipline.description && (
        <p className="line-clamp-2 break-words text-sm text-ink-2">{discipline.description}</p>
      )}
      <div className="mt-auto flex items-center justify-between pt-1">
        <span className="font-display text-xl">
          <b className="font-medium">{formatCredits(discipline.credits)}</b>{" "}
          <small className="font-sans text-xs text-ink-2">{creditsWord(discipline.credits)}</small>
        </span>
        {reviewsUrl && (
          <a
            href={reviewsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg px-3 py-1.5 text-[13px] font-semibold text-ink ring-1 ring-inset ring-rule transition-[transform,background-color] duration-150 ease-out hover:bg-paper active:scale-[.97] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt"
          >
            Відгуки ↗
          </a>
        )}
      </div>
    </Card>
  );
}
