// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: moderation.test.tsx.
import { useState } from "react";
import type { ModerationItem } from "../../../api/types";
import { Badge } from "../../../ui/Badge";
import { Button } from "../../../ui/Button";
import { Card } from "../../../ui/Card";
import { describeDiff } from "./useModeration";

const TYPE_VIEW = {
  add: { tone: "ok", label: "Додавання" },
  update: { tone: "info", label: "Зміна" },
  remove: { tone: "warn", label: "Видалення" },
} as const;

export function ItemCard({
  item,
  selected,
  onSelect,
  onApprove,
  onReject,
  busy,
}: {
  item: ModerationItem;
  selected: boolean;
  /** Є лише для записів у черзі. */
  onSelect?: (checked: boolean) => void;
  onApprove: () => void;
  onReject: (reason: string) => void;
  busy: boolean;
}) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const view = TYPE_VIEW[item.change_type];
  const title = typeof item.payload.title === "string" ? item.payload.title : null;
  const pending = item.status === "pending";

  return (
    <Card role="group" aria-label={`Запис ${item.id}`} className="rise flex gap-3">
      {onSelect && (
        <input
          type="checkbox"
          aria-label={`Вибрати запис ${item.id}`}
          checked={selected}
          onChange={(event) => onSelect(event.target.checked)}
          className="mt-1 size-4 shrink-0 accent-cobalt"
        />
      )}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={view.tone}>{view.label}</Badge>
          <span className="font-medium">
            {title ?? (item.course_id !== null ? `Дисципліна #${item.course_id}` : "Нова дисципліна")}
          </span>
        </div>
        <ul className="mt-2 space-y-0.5 text-ink-2">
          {describeDiff(item).map((line) => (
            <li key={line} className="break-words">
              {line}
            </li>
          ))}
        </ul>
        {!pending && item.reviewed_by && (
          <p className="mt-2 text-sm text-ink-2">Розглянув: {item.reviewed_by.full_name}</p>
        )}
        {pending && rejecting && (
          <div className="mt-3 flex flex-wrap items-end gap-2">
            <label className="flex min-w-[220px] flex-1 flex-col gap-1 text-sm font-medium">
              Причина (необов'язково)
              <input
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                className="rounded-[10px] border border-rule bg-surface px-3 py-2 font-normal"
              />
            </label>
            <Button variant="danger" size="sm" disabled={busy} onClick={() => onReject(reason.trim())}>
              Підтвердити відхилення
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setRejecting(false)}>
              Скасувати
            </Button>
          </div>
        )}
      </div>
      {pending && !rejecting && (
        <div className="flex shrink-0 flex-col gap-2 self-start sm:flex-row">
          <Button size="sm" disabled={busy} onClick={onApprove}>
            Схвалити
          </Button>
          <Button variant="ghost" size="sm" disabled={busy} onClick={() => setRejecting(true)}>
            Відхилити
          </Button>
        </div>
      )}
    </Card>
  );
}
