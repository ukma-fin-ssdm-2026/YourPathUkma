// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: plans.test.tsx.
import { useMemo, useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import { ApiError } from "../../api/errors";
import type { PlanResponse } from "../../api/types";
import { formatCredits } from "../../lib/credits";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { StatusBadge } from "../../ui/Badge";
import { linkButtonClass, linkButtonSmClass, linkGhostClass } from "../../ui/linkButton";
import { ConfirmDialog } from "./ConfirmDialog";
import { courseHeading, groupPlansByCourse } from "./groupPlans";
import { useDeletePlan, usePlans } from "./usePlans";

const LEVEL_LABEL = { low: "низьке", medium: "середнє", high: "високе" } as const;
const LEVEL_OPACITY = { low: 0.35, medium: 0.7, high: 1 } as const;
const SEASONS = [
  { key: "autumn", label: "осінь", color: "bg-autumn" },
  { key: "spring", label: "весна", color: "bg-spring" },
  { key: "summer", label: "літо", color: "bg-summer" },
] as const;

function LoadDots({ levels }: { levels: PlanResponse["load_levels"] }) {
  const summary = SEASONS.map((s) => `${s.label} ${LEVEL_LABEL[levels[s.key] ?? "medium"]}`).join(", ");
  return (
    <span role="img" aria-label={`Навантаження: ${summary}`} className="inline-flex gap-1">
      {SEASONS.map((s) => (
        <i
          key={s.key}
          className={`block size-2.5 rounded-full ${s.color}`}
          style={{ opacity: LEVEL_OPACITY[levels[s.key] ?? "medium"] }}
        />
      ))}
    </span>
  );
}

function deleteMessage(error: ApiError): string {
  if (error.code === "PLAN_NOT_DELETABLE") return "Видаляти можна лише чернетки";
  if (error.status === 403 || error.status === 404) return "План не знайдено";
  return error.message;
}

export function PlansPage({ mode }: { mode: "all" | "saved" }) {
  const plans = usePlans(mode === "saved" ? "draft" : undefined);
  const remove = useDeletePlan();
  const [target, setTarget] = useState<PlanResponse | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const groups = useMemo(() => groupPlansByCourse(plans.data?.plans ?? []), [plans.data]);

  function confirmDelete() {
    if (!target) return;
    remove.mutate(target.id, {
      onSuccess: () => {
        toast.success("План видалено");
        setTarget(null);
      },
      onError: (error) => {
        setNotice(deleteMessage(error));
        setTarget(null);
      },
    });
  }

  let content;
  if (plans.isPending) {
    content = <div aria-busy="true" aria-label="Завантажуємо плани" className="h-40 animate-pulse rounded-2xl bg-rule" />;
  } else if (plans.isError) {
    const error = plans.error;
    content = (
      <div role="alert" className="rounded-2xl bg-bad-bg p-5 text-bad">
        <p>{error instanceof ApiError ? error.message : "Не вдалося завантажити плани"}</p>
        {error instanceof ApiError && error.requestId && <p className="mt-1 text-sm">Код помилки: {error.requestId}</p>}
      </div>
    );
  } else if (groups.length === 0) {
    content = (
      <div className="grid justify-items-center gap-3 rounded-2xl border-2 border-dashed border-rule p-10 text-center">
        <p className="font-display text-base">У вас ще немає планів</p>
        <p className="text-ink-2">Створіть перший план вибіркових дисциплін на рік.</p>
        <Link to="/path/create" className={linkButtonClass}>
          Створити план
        </Link>
      </div>
    );
  } else {
    content = (
      <Card className="overflow-x-auto p-2">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="text-[13px] text-ink-2">
              <th className="px-3.5 py-2.5 font-medium">План</th>
              <th className="px-3.5 py-2.5 font-medium">Навантаження</th>
              <th className="px-3.5 py-2.5 font-medium">Статус</th>
              <th className="px-3.5 py-2.5 text-right font-medium">Кредити</th>
              <th className="px-3.5 py-2.5 text-right font-medium">Вільний вибір</th>
              <th className="px-3.5 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {groups.flatMap((group) => [
              <tr key={`h-${group.academic_year}`}>
                <th colSpan={6} scope="colgroup" className="bg-paper px-3.5 py-2 text-[13px] font-semibold text-ink-2">
                  {courseHeading(group)}
                </th>
              </tr>,
              ...group.plans.map((plan) => (
                <tr key={plan.id} data-testid={`plan-${plan.id}`} className="border-b border-rule last:border-b-0">
                  <td className="px-3.5 py-3">
                    <b className="font-semibold">
                      План {plan.academic_year}/{plan.academic_year + 1}
                    </b>
                    <small className="block text-[13px] text-ink-2">
                      створено {new Date(plan.created_at).toLocaleDateString("uk-UA")}
                    </small>
                  </td>
                  <td className="px-3.5 py-3">
                    <LoadDots levels={plan.load_levels} />
                  </td>
                  <td className="px-3.5 py-3">
                    <StatusBadge status={plan.status} />
                  </td>
                  <td className="px-3.5 py-3 text-right tabular-nums">{formatCredits(plan.total_credits)}</td>
                  <td className="px-3.5 py-3 text-right tabular-nums">{formatCredits(plan.free_elective_credits)}</td>
                  <td className="px-3.5 py-3">
                    <div className="flex justify-end gap-2">
                      {plan.status === "draft" ? (
                        <>
                          <Link to={`/path/create?plan=${plan.id}`} className={linkButtonSmClass}>
                            Редагувати
                          </Link>
                          <Button
                            variant="danger"
                            size="sm"
                            onClick={() => {
                              setNotice(null);
                              setTarget(plan);
                            }}
                          >
                            Видалити
                          </Button>
                        </>
                      ) : (
                        <Link to={`/path/plan/${plan.id}`} className={linkGhostClass}>
                          Переглянути
                        </Link>
                      )}
                    </div>
                  </td>
                </tr>
              )),
            ])}
          </tbody>
        </table>
      </Card>
    );
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-[22px]">{mode === "saved" ? "Збережені плани" : "Індивідуальний план"}</h1>
        <div className="flex gap-2.5">
          {mode === "all" && (
            <Button variant="ghost" disabled title="Синхронізація з САЗ поки недоступна">
              Оновити з САЗ
            </Button>
          )}
          <Link to="/path/create" className={linkButtonClass}>
            Новий план
          </Link>
        </div>
      </div>
      {notice && (
        <p role="alert" className="rounded-[10px] bg-bad-bg px-4 py-3 text-bad">
          {notice}
        </p>
      )}
      {content}
      <ConfirmDialog
        open={target !== null}
        title="Видалити план?"
        description={target ? `План ${target.academic_year}/${target.academic_year + 1} буде видалено без можливості відновлення.` : undefined}
        confirmLabel="Видалити"
        busy={remove.isPending}
        onConfirm={confirmDelete}
        onCancel={() => setTarget(null)}
      />
    </div>
  );
}
