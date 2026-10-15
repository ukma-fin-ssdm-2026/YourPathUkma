// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: audit.test.tsx.
import { Fragment, useState } from "react";
import { formatDateTime } from "../../../lib/datetime";
import { Badge } from "../../../ui/Badge";
import { Button } from "../../../ui/Button";
import { Segmented } from "../../../ui/Segmented";
import { Pagination } from "../../catalog/Pagination";
import { useDebouncedValue } from "../../catalog/useDebouncedValue";
import { AUDIT_PAGE_SIZE, type AuditOutcome, outcomeLabel, useAuditEntry, useAuditLog } from "./useAudit";

const OUTCOME_OPTIONS: { value: AuditOutcome | "all"; label: string }[] = [
  { value: "all", label: "Усі" },
  { value: "allowed", label: "Дозволено" },
  { value: "denied", label: "Відмовлено" },
];

const CELL = "px-3 py-2 text-left align-top";

const text = (value: unknown) => (value === undefined ? "—" : JSON.stringify(value, null, 2));

function EntryDetails({ id }: { id: number }) {
  const entry = useAuditEntry(id);
  return (
    <section aria-label={`Деталі запису ${id}`} className="grid gap-3 p-3 sm:grid-cols-2">
      {entry.isError && <p className="text-bad sm:col-span-2">Не вдалося завантажити деталі</p>}
      {entry.isPending && <p className="text-ink-2 sm:col-span-2">Завантаження…</p>}
      {entry.data && (
        <>
          <div className="min-w-0">
            <h3 className="font-medium">Було</h3>
            <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words text-sm">{text(entry.data.old_value)}</pre>
          </div>
          <div className="min-w-0">
            <h3 className="font-medium">Стало</h3>
            <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words text-sm">{text(entry.data.new_value)}</pre>
          </div>
        </>
      )}
    </section>
  );
}

export function AuditPage() {
  const [action, setAction] = useState("");
  const [outcome, setOutcome] = useState<AuditOutcome | "all">("all");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<number | null>(null);
  const debouncedAction = useDebouncedValue(action.trim(), 250);
  const log = useAuditLog({ action: debouncedAction, outcome: outcome === "all" ? undefined : outcome, page });
  const list = log.data?.audit_log ?? [];

  return (
    <section aria-label="Журнал дій">
      <h1 className="font-display text-[22px]">Журнал дій</h1>
      <div className="mt-4 flex flex-wrap items-end gap-3">
        <label className="flex min-w-[220px] flex-col gap-1 font-medium">
          Дія
          <input
            value={action}
            placeholder="наприклад, plan.read"
            onChange={(event) => {
              setAction(event.target.value);
              setPage(1);
            }}
            className="rounded-[10px] border border-rule bg-surface px-3 py-2 font-normal"
          />
        </label>
        <Segmented
          ariaLabel="Результат"
          value={outcome}
          options={OUTCOME_OPTIONS}
          onChange={(value) => {
            setOutcome(value);
            setPage(1);
          }}
        />
      </div>

      <div className="mt-4 overflow-x-auto">
        {log.isError ? (
          <p role="alert" className="text-bad">
            Не вдалося завантажити журнал
          </p>
        ) : log.isSuccess && list.length === 0 ? (
          <p className="text-ink-2">Записів немає</p>
        ) : (
          <table className="w-full min-w-[760px] border-collapse">
            <thead>
              <tr className="border-b border-rule text-ink-2">
                <th className={CELL}>Час</th>
                <th className={CELL}>Виконавець</th>
                <th className={CELL}>Дія</th>
                <th className={CELL}>Об'єкт</th>
                <th className={CELL}>Результат</th>
                <th className={CELL}>IP</th>
                <th className={CELL}>
                  <span className="sr-only">Деталі</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {list.map((entry) => (
                <Fragment key={entry.id}>
                  <tr className="border-b border-rule">
                    <td className={CELL}>{formatDateTime(entry.created_at)}</td>
                    <td className={`${CELL} break-words`}>{entry.actor?.full_name ?? "Анонімно"}</td>
                    <td className={`${CELL} break-words`}>{entry.action}</td>
                    <td className={CELL}>{`${entry.object_type} #${entry.object_id}`}</td>
                    <td className={CELL}>
                      <Badge tone={entry.outcome === "allowed" ? "ok" : "bad"}>{outcomeLabel(entry.outcome)}</Badge>
                    </td>
                    <td className={CELL}>{entry.ip}</td>
                    <td className={CELL}>
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-expanded={openId === entry.id}
                        onClick={() => setOpenId(openId === entry.id ? null : entry.id)}
                      >
                        Деталі
                      </Button>
                    </td>
                  </tr>
                  {openId === entry.id && (
                    <tr className="border-b border-rule bg-paper">
                      <td colSpan={7}>
                        <EntryDetails id={entry.id} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {log.data && (
        <Pagination page={page} pageSize={AUDIT_PAGE_SIZE} total={log.data.pagination.total} onPage={setPage} />
      )}
    </section>
  );
}
