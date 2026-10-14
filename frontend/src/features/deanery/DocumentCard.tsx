// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: documents.test.tsx.
import type { DeaneryDocument } from "../../api/types";
import { formatBytes } from "../../lib/bytes";
import { Badge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { useDeaneryDocument } from "./useDeanery";

const STATUS = {
  pending: { tone: "warn", label: "Розпізнаємо…" },
  parsed: { tone: "ok", label: "Розпізнано" },
  failed: { tone: "bad", label: "Не розпізнано" },
} as const;

export function DocumentCard({
  doc,
  selected,
  pollMs,
  onSelect,
  onDelete,
}: {
  doc: DeaneryDocument;
  selected: boolean;
  pollMs?: number;
  onSelect: (id: number) => void;
  onDelete: (doc: DeaneryDocument) => void;
}) {
  // Поки документ розпізнається, цей хук опитує сервер; готовий статус береться з нього.
  const live = useDeaneryDocument(doc.parse_status === "pending" ? doc.id : null, { pollMs });
  const current = live.data ?? doc;
  const status = STATUS[current.parse_status];
  return (
    <div
      data-testid={`doc-${doc.id}`}
      className={
        "grid grid-cols-[auto_1fr_auto] items-center gap-3.5 rounded-xl border bg-surface px-4 py-3.5 " +
        (selected ? "border-cobalt" : "border-rule")
      }
    >
      <div
        aria-hidden="true"
        className="grid h-12 w-10 place-items-center rounded-md bg-paper font-display text-[11px] text-ink-2 ring-1 ring-inset ring-rule"
      >
        {current.mime_type.toUpperCase()}
      </div>
      <div className="min-w-0">
        <button
          type="button"
          onClick={() => onSelect(doc.id)}
          className="max-w-full break-words text-left font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt"
        >
          {current.original_filename}
        </button>{" "}
        <Badge tone={status.tone}>{status.label}</Badge>
        <small className="block text-ink-2">{formatBytes(current.size_bytes)}</small>
        {current.parse_status === "pending" && (
          <div aria-hidden="true" className="mt-2 grid gap-1.5">
            <i className="block h-2.5 w-3/5 animate-pulse rounded-full bg-rule" />
            <i className="block h-2.5 w-2/5 animate-pulse rounded-full bg-rule" />
          </div>
        )}
        {current.parse_status === "failed" && current.parse_error && (
          <p className="mt-1 text-sm text-bad">{current.parse_error}</p>
        )}
      </div>
      <Button
        variant="danger"
        size="sm"
        disabled={current.parse_status === "pending"}
        onClick={() => onDelete(current)}
      >
        Видалити
      </Button>
    </div>
  );
}
