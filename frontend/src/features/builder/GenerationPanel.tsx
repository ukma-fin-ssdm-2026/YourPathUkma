// Використання ШІ: Codex створив блок стану генерації. Перевірка: Vitest і Chromium.
import { formatCredits } from "../../lib/credits";
import { Button } from "../../ui/Button";
import { usePlan } from "./useBuilderData";
import { generationStartError, type usePlanGeneration } from "./usePlanGeneration";

export function GenerationPanel({
  task,
  onOpen,
}: {
  task: ReturnType<typeof usePlanGeneration>;
  onOpen: (id: number) => void;
}) {
  const { generation, startError, statusError, starting, checking, checkStatus, openDraft } = task;
  const planId = generation?.status === "succeeded" ? generation.plan_id ?? null : null;
  const ready = planId !== null;
  const result = usePlan(planId);
  if (!starting && !generation && !startError) return null;

  const failed = generation?.status === "failed" || (generation?.status === "succeeded" && !ready);
  const error = startError
    ? generationStartError(startError)
    : statusError
      ? "Не вдалося перевірити стан генерації."
      : failed
        ? "Не вдалося згенерувати план. Спробуйте ще раз."
        : null;
  const heading = error ?? (ready ? "План із ШІ готовий" : "Генеруємо план…");
  return (
    <section
      key={heading}
      aria-label="Генерація плану з ШІ"
      className="rounded-2xl border border-rule bg-info-bg p-4 motion-safe:animate-[rise_240ms_var(--ease-out)_backwards]"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role={error ? "alert" : "status"} className="grid min-w-0 gap-1">
          <h2 className="flex items-center gap-2 font-display text-sm">
            {!ready && !error && (
              <span aria-hidden="true" className="size-4 shrink-0 animate-spin rounded-full border-2 border-cobalt/25 border-t-cobalt motion-reduce:animate-none" />
            )}
            {heading}
          </h2>
          {!ready && !error && (
            <p className="text-sm text-ink-2">Поки готується чернетка, можна редагувати поточний план.</p>
          )}
          {ready && result.data && (
            <p className="text-sm text-ink-2">
              Дисциплін: {result.data.items.length} · Кредитів: {formatCredits(result.data.total_credits)}
            </p>
          )}
        </div>
        {ready && (
          <Button onClick={() => openDraft(onOpen)}>Відкрити чернетку</Button>
        )}
        {statusError && (
          <Button variant="ghost" disabled={checking} onClick={() => void checkStatus()}>
            Перевірити стан
          </Button>
        )}
      </div>
      {!!generation?.notices.length && (
        <ul className="mt-3 grid list-disc gap-1 rounded-[10px] bg-warn-bg py-2.5 pr-3 pl-7 text-sm text-warn">
          {generation.notices.map(({ code, course_id, message }) => (
            <li key={`${code}:${course_id}:${message}`}>{message}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
