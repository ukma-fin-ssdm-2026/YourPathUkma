// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: summary.test.tsx.
import type { Credits, PlanValidationResponse, RuleIssue } from "../../api/types";
import { creditsPercent, formatCredits } from "../../lib/credits";
import { FREE_LIMIT, MIN_YEAR_CREDITS, summarize, type BuilderPlan } from "./plan";

const YEAR_MAX = 60;

const ERROR_TEXT: Record<string, string> = {
  DUPLICATE_COURSE: "Дисципліни в плані не повинні повторюватись",
  ONLY_FREE_ELECTIVES: "Оберіть хоча б одну профорієнтовну дисципліну",
  FREE_ELECTIVE_LIMIT_EXCEEDED: `Перевищено ліміт вільного вибору (${FREE_LIMIT} кредитів)`,
};

const WARNING_TEXT: Record<string, string> = {
  LOW_LOAD_FUTURE_INCREASE: "Низьке навантаження: наступні роки зростуть",
};

function Metric({
  title,
  value,
  of,
  barLabel,
  barValue,
  barMax,
  barClass,
  mark,
}: {
  title: string;
  value: number;
  of: string;
  barLabel: string;
  barValue: number;
  barMax: number;
  barClass: string;
  mark?: number;
}) {
  return (
    <div className="p-4">
      <div className="text-[13px] text-ink-2">{title}</div>
      <div className="font-display text-lg">
        {formatCredits(value)} <small className="font-sans text-[13px] text-ink-2">{of}</small>
      </div>
      <div className="relative mt-2 h-1.5 rounded-full bg-rule">
        <div
          role="progressbar"
          aria-label={barLabel}
          aria-valuemin={0}
          aria-valuemax={barMax}
          aria-valuenow={barValue}
          className={`h-full rounded-full transition-[width] duration-200 ease-out ${barClass}`}
          style={{ width: `${creditsPercent(barValue, barMax)}%` }}
        />
        {mark !== undefined && (
          <u
            aria-hidden="true"
            className="absolute -top-[3px] -bottom-[3px] w-0.5 bg-ink no-underline opacity-55"
            style={{ left: `${mark}%` }}
          />
        )}
      </div>
    </div>
  );
}

export function SummaryStrip({
  plan,
  validation,
  credits,
  normativeCredits,
}: {
  plan: BuilderPlan;
  validation: PlanValidationResponse | undefined;
  credits: Credits | undefined;
  normativeCredits: number;
}) {
  const local = summarize(plan.items);
  const selected = validation?.summary.total_credits ?? local.total;
  const yearTotal = selected + normativeCredits;
  const freeUsed =
    validation?.summary.free_elective_used_all_years ?? (credits?.free_choice_used ?? 0) + local.free;
  const professional = (credits?.professional_used ?? 0) + (local.total - local.free);

  // Сервер не бачить нормативних з документа деканату, тож це попередження рахуємо самі.
  const serverWarnings = (validation?.warnings ?? []).filter((w) => w.code !== "YEAR_CREDITS_BELOW_MIN");
  const warnings: RuleIssue[] = [...serverWarnings];
  if (plan.items.length > 0 && yearTotal < MIN_YEAR_CREDITS) {
    warnings.push({ code: "YEAR_CREDITS_BELOW_MIN", message: "За рік менше 57 кредитів", field: null });
  }
  const errors = validation?.errors ?? [];
  const issues = errors.length + warnings.length;

  return (
    <section aria-label="Підсумок плану" className="grid gap-3">
      <div className="grid divide-rule overflow-hidden rounded-2xl border border-rule bg-surface sm:grid-cols-2 sm:divide-x lg:grid-cols-4">
        <Metric
          title="Кредитів за рік"
          value={yearTotal}
          of={`із ${MIN_YEAR_CREDITS}–${YEAR_MAX}`}
          barLabel="Кредитів за рік"
          barValue={yearTotal}
          barMax={YEAR_MAX}
          barClass="bg-cobalt"
          mark={(MIN_YEAR_CREDITS / YEAR_MAX) * 100}
        />
        <Metric
          title="Вільний вибір за весь час"
          value={freeUsed}
          of={`з ${FREE_LIMIT}`}
          barLabel="Вільний вибір"
          barValue={freeUsed}
          barMax={FREE_LIMIT}
          barClass="bg-violet"
        />
        <Metric
          title="Профорієнтовні"
          value={professional}
          of={`з ${credits?.professional_limit ?? 54}`}
          barLabel="Профорієнтовні"
          barValue={professional}
          barMax={credits?.professional_limit ?? 54}
          barClass="bg-cobalt"
        />
        <div className={"p-4 " + (issues > 0 ? "bg-warn-bg text-warn" : "")}>
          <div className="text-[13px]" data-testid="issues-count">
            {issues > 0 ? (
              <>
                Є попередження: <b>{issues}</b>
              </>
            ) : (
              "Перевірки"
            )}
          </div>
          <div className="mt-1 text-sm font-semibold">
            {issues === 0
              ? "Усе гаразд"
              : (WARNING_TEXT[(errors[0] ?? warnings[0])!.code] ??
                ERROR_TEXT[(errors[0] ?? warnings[0])!.code] ??
                (errors[0] ?? warnings[0])!.message)}
          </div>
        </div>
      </div>

      {errors.length > 0 && (
        <ul role="alert" className="grid gap-1 rounded-[10px] bg-bad-bg px-4 py-3 text-bad">
          {errors.map((issue) => (
            <li key={issue.code}>{ERROR_TEXT[issue.code] ?? issue.message}</li>
          ))}
        </ul>
      )}
      {warnings.length > 0 && (
        <ul className="grid gap-1 rounded-[10px] bg-warn-bg px-4 py-3 text-warn">
          {warnings.map((issue) => (
            <li key={issue.code}>{WARNING_TEXT[issue.code] ?? issue.message}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
