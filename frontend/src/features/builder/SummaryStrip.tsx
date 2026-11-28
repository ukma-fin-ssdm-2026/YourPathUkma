// Використання ШІ: Codex додав серверні години й повноту #291; перевірка: Vitest, typecheck, lint і build.
// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: summary.test.tsx.
// Codex уточнив підсумок кредитів і живу валідацію. Перевірка — фронтенд-тести.
// Codex вніс зміни для issue #221. Перевірка: фронтенд-тести й лінтер.
import type { Credits, PlanValidationResponse, RuleIssue } from "../../api/types";
import { creditsPercent } from "../../lib/credits";
import { CountUp } from "../../ui/CountUp";
import { FREE_LIMIT, MIN_YEAR_CREDITS, summarize, type BuilderPlan } from "./plan";
import { trimesterLabel, type Trimester } from "../../lib/trimester";

const YEAR_MAX = 60;

export const ERROR_TEXT: Record<string, string> = {
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
        <CountUp value={value} /> <small className="font-sans text-[13px] text-ink-2">{of}</small>
      </div>
      <div className="relative mt-2 h-1.5 rounded-full bg-rule">
        <div
          role="progressbar"
          aria-label={barLabel}
          aria-valuemin={0}
          aria-valuemax={barMax}
          aria-valuenow={barValue}
          className={`bar-grow h-full rounded-full ${barClass}`}
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
  showIssues = true,
}: {
  plan: BuilderPlan;
  validation: PlanValidationResponse | undefined;
  credits: Credits | undefined;
  normativeCredits: number;
  /** false: попередження й помилки не показуються. Конструктор вмикає їх, коли студент зберігає чи подає план. */
  showIssues?: boolean;
}) {
  const local = summarize(plan.items);
  const currentValidation = plan.items.length > 0 ? validation : undefined;
  const selected = currentValidation?.summary.total_credits ?? local.total;
  const yearTotal = currentValidation?.summary.year_total_credits ?? selected + normativeCredits;
  const freeUsed = (credits?.free_choice_used ?? 0) + local.free;
  const professional = (credits?.professional_used ?? 0) + (local.total - local.free);

  const warnings: RuleIssue[] = [...(currentValidation?.warnings ?? [])];
  if (!currentValidation && plan.items.length > 0 && yearTotal < MIN_YEAR_CREDITS) {
    warnings.push({
      code: "YEAR_CREDITS_BELOW_MIN",
      message: "За рік менше 57 кредитів",
      field: null,
    });
  }
  const errors = showIssues ? (currentValidation?.errors ?? []) : [];
  if (!showIssues) warnings.length = 0;
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
              ? showIssues
                ? currentValidation?.valid
                  ? "Усе гаразд"
                  : "Перевірка ще не завершена"
                : "Виконаються під час збереження"
              : (WARNING_TEXT[(errors[0] ?? warnings[0])!.code] ??
                ERROR_TEXT[(errors[0] ?? warnings[0])!.code] ??
                (errors[0] ?? warnings[0])!.message)}
          </div>
        </div>
      </div>

      <div
        className="rounded-2xl border border-rule bg-surface p-4"
        aria-label="Тижневе навантаження"
      >
        <h2 className="text-sm font-semibold">Години на тиждень · максимум 25</h2>
        <p className="mt-1 text-xs text-ink-2">
          Контактні години із САЗ разом із нормативними дисциплінами. 60 ECTS — річний орієнтир, а
          не верхня межа.
        </p>
        <dl className="mt-3 grid gap-3 sm:grid-cols-3" aria-live="polite">
          {([1, 2, 3] as Trimester[]).map((tri) => {
            const load = currentValidation?.summary.workload_by_trimester?.[String(tri)];
            const over = (load?.known_weekly_hours ?? 0) > 25;
            return (
              <div key={tri} className={over ? "text-bad" : ""}>
                <dt className="text-xs text-ink-2">{trimesterLabel(tri)}</dt>
                <dd className="mt-1 text-sm font-semibold">
                  {load ? `${load.known_weekly_hours} год/тиждень` : "Очікуємо перевірку"}
                  {load && !load.complete ? " · неповні дані" : ""}
                  {over ? " · перевищено 25" : ""}
                </dd>
                {load?.level && (
                  <dd className="text-xs text-ink-2">
                    {{ low: "Низьке", medium: "Середнє", high: "Високе" }[load.level] ?? load.level}
                  </dd>
                )}
                {!!load?.missing_courses.length && (
                  <dd className="mt-1 text-xs text-ink-2">
                    Без годин: {load.missing_courses.map((c) => c.title).join(", ")}
                  </dd>
                )}
              </div>
            );
          })}
        </dl>
      </div>

      {errors.length > 0 && (
        <ul role="alert" className="rise grid gap-1 rounded-[10px] bg-bad-bg px-4 py-3 text-bad">
          {errors.map((issue) => (
            <li key={issue.code}>{ERROR_TEXT[issue.code] ?? issue.message}</li>
          ))}
        </ul>
      )}
      {warnings.length > 0 && (
        <ul className="rise grid gap-1 rounded-[10px] bg-warn-bg px-4 py-3 text-warn">
          {warnings.map((issue) => (
            <li key={issue.code}>{WARNING_TEXT[issue.code] ?? issue.message}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
