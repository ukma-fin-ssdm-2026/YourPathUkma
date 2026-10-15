// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: profile.test.tsx.
import type { AcademicYear } from "../../api/types";
import { formatCredits } from "../../lib/credits";
import { buildLedgerRow, sumByCategory } from "./ledger";

const COURSES = [1, 2, 3, 4];

const TONES = {
  normative: "bg-normative",
  professional: "bg-cobalt",
  free_choice: "bg-violet",
  empty: "bg-rule",
} as const;

function academicYearLabel(year: number): string {
  return `${year}/${String(year + 1).slice(2)}`;
}

function Row({ course, data }: { course: number; data: AcademicYear | undefined }) {
  const row = buildLedgerRow(data?.records ?? []);
  const cells = (Object.keys(TONES) as (keyof typeof TONES)[]).flatMap((tone) =>
    Array.from({ length: row[tone] }, (_, index) => <i key={`${tone}-${index}`} className={`block aspect-square rounded-[2px] ${TONES[tone]}`} />),
  );
  return (
    <div className="grid grid-cols-[78px_1fr_64px] items-center gap-4">
      <div className="font-semibold">
        {course} курс
        <small className="block text-xs font-normal text-ink-2">
          {data ? academicYearLabel(data.academic_year) : " "}
        </small>
      </div>
      <div className="grid grid-cols-[repeat(60,1fr)] gap-0.5" aria-hidden="true">
        {cells}
      </div>
      <div className="text-right font-semibold">{data ? formatCredits(data.total_credits) : "—"}</div>
    </div>
  );
}

export function CreditsLedger({ years }: { years: AcademicYear[] }) {
  const totals = sumByCategory(years.flatMap((year) => year.records));
  const total = totals.normative + totals.professional + totals.free_choice;
  const summary =
    `Набрано ${formatCredits(total)} кредитів: нормативні ${formatCredits(totals.normative)}, ` +
    `профорієнтовні ${formatCredits(totals.professional)}, вільний вибір ${formatCredits(totals.free_choice)}`;
  const legend = [
    { tone: TONES.normative, label: "Нормативні", value: totals.normative },
    { tone: TONES.professional, label: "Профорієнтовні", value: totals.professional },
    { tone: TONES.free_choice, label: "Вільний вибір", value: totals.free_choice },
  ];
  return (
    <div>
      <div role="img" aria-label={summary} className="grid gap-3">
        {COURSES.map((course) => (
          <Row key={course} course={course} data={years.find((year) => year.course_year === course)} />
        ))}
      </div>
      <ul className="mt-6 flex flex-wrap gap-7 border-t border-rule pt-5">
        {legend.map((item) => (
          <li key={item.label} className="flex items-center gap-2.5">
            <i aria-hidden="true" className={`block size-3 rounded-[3px] ${item.tone}`} />
            <b className="font-semibold">{item.label}</b>
            <span className="text-ink-2">{formatCredits(item.value)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
