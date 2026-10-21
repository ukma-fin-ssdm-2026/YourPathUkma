// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: view.test.tsx.
import type { CSSProperties } from "react";
import { Link, useParams } from "react-router";
import { useConfig } from "../../api/config";
import { ApiError } from "../../api/errors";
import type { LoadLevel, PlanResponse } from "../../api/types";
import { formatCredits } from "../../lib/credits";
import { trimesterKey, trimesterLabel, type Trimester } from "../../lib/trimester";
import { StatusBadge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { CountUp } from "../../ui/CountUp";
import { linkButtonClass, linkGhostClass } from "../../ui/linkButton";
import { usePlan } from "../builder/useBuilderData";
import { useExportPlan } from "./useExportPlan";

const STATUS_NOTE: Record<PlanResponse["status"], string> = {
  draft: "Чернетка: ще можна редагувати",
  submitted: "Подано на розгляд",
  awaiting_deanery: "Очікує на затвердження деканатом",
  approved: "Затверджено деканатом",
};

const LEVEL_LABEL: Record<LoadLevel, string> = { low: "низьке", medium: "середнє", high: "високе" };

function NotFound() {
  return (
    <Card className="grid justify-items-start gap-3">
      <p>План не знайдено</p>
      <Link to="/path/plan" className={linkGhostClass}>
        Індивідуальний план
      </Link>
    </Card>
  );
}

function Metric({ title, value }: { title: string; value: number }) {
  return (
    <div className="p-4">
      <div className="text-[13px] text-ink-2">{title}</div>
      <div className="font-display text-xl">
        <CountUp value={value} />
      </div>
    </div>
  );
}

export function PlanViewPage() {
  const { id } = useParams();
  const planId = id && /^\d+$/.test(id) ? Number(id) : null;
  const query = usePlan(planId);
  const config = useConfig();
  const exportPlan = useExportPlan();

  if (planId === null) return <NotFound />;
  if (query.isError) {
    const error = query.error;
    if (error instanceof ApiError && (error.status === 404 || error.status === 403)) return <NotFound />;
    return (
      <p role="alert" className="text-bad">
        {error instanceof ApiError ? error.message : "Не вдалося завантажити план"}
      </p>
    );
  }
  const plan = query.data;
  if (!plan) {
    return (
      <p role="status" className="text-ink-2">
        Завантаження…
      </p>
    );
  }

  const exportError = exportPlan.error;
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex flex-wrap items-center gap-3 font-display text-[22px]">
            План на {plan.academic_year}/{plan.academic_year + 1}
            <StatusBadge status={plan.status} />
          </h1>
          <p className="mt-1 text-ink-2">
            <span>{STATUS_NOTE[plan.status]}</span> · створено{" "}
            {new Date(plan.created_at).toLocaleDateString("uk-UA")}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          {plan.status === "draft" && (
            <Link to={`/path/create?plan=${plan.id}`} className={linkButtonClass}>
              Редагувати
            </Link>
          )}
          {config.data?.features.plan_export && (
            <Button
              variant="ghost"
              disabled={exportPlan.isPending}
              onClick={() => exportPlan.mutate({ id: plan.id, academicYear: plan.academic_year })}
            >
              {exportPlan.isPending ? "Готуємо PDF…" : "Експорт PDF"}
            </Button>
          )}
          {config.data?.reviews_url && (
            <a href={config.data.reviews_url} target="_blank" rel="noopener noreferrer" className={linkGhostClass}>
              Почитати відгуки ↗
            </a>
          )}
          <Link to="/path/plan" className={linkGhostClass}>
            До списку планів
          </Link>
        </div>
      </div>

      {exportError && (
        <p role="alert" className="rounded-[10px] bg-bad-bg px-4 py-3 text-bad">
          Не вдалося підготувати PDF: {exportError.message}
          {exportError.requestId && <span className="block text-sm">Код помилки: {exportError.requestId}</span>}
        </p>
      )}

      <div className="grid divide-rule overflow-hidden rounded-2xl border border-rule bg-surface sm:grid-cols-3 sm:divide-x">
        <Metric title="Кредитів у плані" value={plan.total_credits} />
        <Metric title="Вільний вибір" value={plan.free_elective_credits} />
        <Metric title="Дисциплін" value={plan.items.length} />
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        {([1, 2, 3] as Trimester[]).map((trimester) => {
          const items = plan.items.filter((item) => item.trimester === trimester);
          const subtotal = items.reduce((sum, item) => sum + item.credits, 0);
          const level = plan.load_levels[trimesterKey(trimester)] ?? "medium";
          return (
            <section
              key={trimester}
              aria-label={trimesterLabel(trimester)}
              className="rise grid content-start gap-2 rounded-2xl border border-rule bg-surface p-3"
              style={{ "--i": trimester } as CSSProperties}
            >
              <div className="flex items-baseline justify-between">
                <h2 className="font-display text-[15px]">{trimesterLabel(trimester)}</h2>
                <span className="text-[13px] text-ink-2">{formatCredits(subtotal)} кр.</span>
              </div>
              <p className="text-[13px] text-ink-2">Навантаження: {LEVEL_LABEL[level]}</p>
              {items.length === 0 ? (
                <p className="rounded-[10px] border-[1.5px] border-dashed border-rule px-3 py-3.5 text-center text-[13px] text-ink-2">
                  Дисциплін немає
                </p>
              ) : (
                <ul className="grid gap-2">
                  {items.map((item) => (
                    <li
                      key={item.course_id}
                      className={
                        "flex items-start justify-between gap-2 rounded-[10px] bg-paper px-3 py-2.5 transition-[translate] duration-200 ease-out hover:-translate-y-0.5 " +
                        (item.is_free_elective ? "shadow-[inset_3px_0_0_var(--violet)]" : "")
                      }
                    >
                      <div className="min-w-0">
                        <span className="break-words font-medium">{item.title}</span>
                        {item.is_free_elective && <small className="block text-xs text-violet-text">вільний вибір</small>}
                      </div>
                      <b className="font-display text-sm">{formatCredits(item.credits)}</b>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          );
        })}
      </div>
    </div>
  );
}
