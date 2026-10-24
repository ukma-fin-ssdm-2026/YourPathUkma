// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: moderation.test.tsx.
import { useState } from "react";
import type { ApiError } from "../../../api/errors";
import type { BulkReviewResult } from "../../../api/types";
import { Button } from "../../../ui/Button";
import { Segmented } from "../../../ui/Segmented";
import { Pagination } from "../../catalog/Pagination";
import { ItemCard } from "./ItemCard";
import {
  type ChangeType,
  type Decision,
  MODERATION_PAGE_SIZE,
  type ModerationStatus,
  useBulkReview,
  useModerationItems,
  useReviewItem,
} from "./useModeration";
import { toast } from "sonner";

const STATUS_OPTIONS: { value: ModerationStatus; label: string }[] = [
  { value: "pending", label: "Очікують" },
  { value: "approved", label: "Схвалені" },
  { value: "rejected", label: "Відхилені" },
];

const TYPE_OPTIONS: { value: ChangeType | "all"; label: string }[] = [
  { value: "all", label: "Усі" },
  { value: "add", label: "Додавання" },
  { value: "update", label: "Зміна" },
  { value: "remove", label: "Видалення" },
];

const SKIP_REASON: Record<string, string> = {
  MODERATION_ITEM_ALREADY_REVIEWED: "уже розглянуто",
  MODERATION_ITEM_NOT_FOUND: "запису немає",
};

function summarize(result: BulkReviewResult): { text: string; skipped: string[] } {
  const parts = [
    result.approved.length > 0 && `схвалено ${result.approved.length}`,
    result.rejected.length > 0 && `відхилено ${result.rejected.length}`,
    result.skipped.length > 0 && `пропущено ${result.skipped.length}`,
  ].filter(Boolean) as string[];
  const text = parts.join(", ");
  return {
    text: text.charAt(0).toUpperCase() + text.slice(1),
    skipped: result.skipped.map(
      (s) => `Запис #${s.id} пропущено: ${SKIP_REASON[s.code] ?? s.code}`,
    ),
  };
}

export function ModerationPage() {
  const [status, setStatus] = useState<ModerationStatus>("pending");
  const [type, setType] = useState<ChangeType | "all">("all");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<{ text: string; skipped: string[] } | null>(null);

  const items = useModerationItems({ status, changeType: type === "all" ? undefined : type, page });
  const review = useReviewItem();
  const bulk = useBulkReview();
  const list = items.data?.moderation_items ?? [];
  const lastPage = Math.max(
    1,
    Math.ceil((items.data?.pagination.total ?? 0) / MODERATION_PAGE_SIZE),
  );
  const busy = review.isPending || bulk.isPending;
  const selectable = status === "pending";

  // Після розгляду останнього запису сторінки повертаємося на останню наявну.
  if (items.data && page > lastPage) setPage(lastPage);

  const resetView = () => {
    setSelected(new Set());
    setError(null);
    setSummary(null);
    setPage(1);
  };

  const decide = (id: number, decision: Decision, reason?: string) => {
    setError(null);
    setSummary(null);
    review.mutate(
      { id, decision, reason },
      {
        onSuccess: () => {
          setSelected((prev) => new Set([...prev].filter((x) => x !== id)));
          toast.success(decision === "approve" ? "Запис схвалено" : "Запис відхилено");
        },
        onError: (e: ApiError) =>
          setError(
            e.code === "MODERATION_ITEM_ALREADY_REVIEWED" ? "Запис уже розглянуто" : e.message,
          ),
      },
    );
  };

  const decideSelected = (decision: Decision) => {
    setError(null);
    bulk.mutate(
      { item_ids: [...selected], decision },
      {
        onSuccess: (result) => {
          setSelected(new Set());
          setSummary(summarize(result));
        },
        onError: (e: ApiError) => setError(e.message),
      },
    );
  };

  const toggle = (id: number, checked: boolean) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });

  const allSelected = list.length > 0 && list.every((item) => selected.has(item.id));

  return (
    <section aria-label="Модерація">
      <h1 className="font-display text-[22px]">Модерація</h1>
      <div className="mt-4 flex flex-wrap gap-3">
        <Segmented
          ariaLabel="Статус записів"
          value={status}
          options={STATUS_OPTIONS}
          onChange={(value) => {
            setStatus(value);
            resetView();
          }}
        />
        <Segmented
          ariaLabel="Тип зміни"
          value={type}
          options={TYPE_OPTIONS}
          onChange={(value) => {
            setType(value);
            resetView();
          }}
        />
      </div>

      {error && (
        <p role="alert" className="mt-4 text-bad">
          {error}
        </p>
      )}
      {summary && (
        <div role="status" className="mt-4 rounded-[10px] bg-info-bg p-3 text-cobalt">
          <p className="font-medium">{summary.text}</p>
          {summary.skipped.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
      )}

      {selectable && list.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 font-medium">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={(event) =>
                setSelected(event.target.checked ? new Set(list.map((item) => item.id)) : new Set())
              }
              className="size-4 accent-cobalt"
            />
            Вибрати всі
          </label>
          {selected.size > 0 && (
            <>
              <Button size="sm" disabled={busy} onClick={() => decideSelected("approve")}>
                Схвалити вибрані ({selected.size})
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={busy}
                onClick={() => decideSelected("reject")}
              >
                Відхилити вибрані ({selected.size})
              </Button>
            </>
          )}
        </div>
      )}

      <div className="mt-4 space-y-3">
        {items.isError && (
          <p role="alert" className="text-bad">
            Не вдалося завантажити чергу
          </p>
        )}
        {items.isSuccess && list.length === 0 && <p className="text-ink-2">Черга порожня</p>}
        {list.map((item) => (
          <ItemCard
            key={item.id}
            item={item}
            busy={busy}
            selected={selected.has(item.id)}
            onSelect={selectable ? (checked) => toggle(item.id, checked) : undefined}
            onApprove={() => decide(item.id, "approve")}
            onReject={(reason) => decide(item.id, "reject", reason || undefined)}
          />
        ))}
      </div>
      {items.data && (
        <Pagination
          page={page}
          pageSize={MODERATION_PAGE_SIZE}
          total={items.data.pagination.total}
          onPage={(next) => {
            setPage(next);
            setSelected(new Set());
          }}
        />
      )}
    </section>
  );
}
