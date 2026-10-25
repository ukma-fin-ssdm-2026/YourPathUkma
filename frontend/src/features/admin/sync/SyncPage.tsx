// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: sync.test.tsx.
import { useState } from "react";
import { useConfig } from "../../../api/config";
import type { SyncJob } from "../../../api/types";
import { formatDateTime } from "../../../lib/datetime";
import { Badge } from "../../../ui/Badge";
import { Button } from "../../../ui/Button";
import { Card } from "../../../ui/Card";
import { Pagination } from "../../catalog/Pagination";
import {
  SYNC_PAGE_SIZE,
  type SyncSource,
  syncStatusLabel,
  useRunSync,
  useSyncJobs,
} from "./useSync";
import { toast } from "sonner";

const SOURCE_LABEL: Record<SyncSource, string> = {
  saz_catalog: "Каталог САЗ",
  faculty_certificates: "Сертифікатні програми",
};

const STATUS_TONE: Record<SyncJob["status"], "neutral" | "info" | "ok" | "bad"> = {
  queued: "neutral",
  running: "info",
  succeeded: "ok",
  failed: "bad",
};

const CELL = "px-3 py-2 text-left align-top";

export function SyncPage({ pollMs }: { pollMs?: number }) {
  const [page, setPage] = useState(1);
  const [source, setSource] = useState<SyncSource>("saz_catalog");
  const config = useConfig();
  const jobs = useSyncJobs(page, pollMs);
  const run = useRunSync();
  const sources: SyncSource[] = config.data?.features.certificate_programs
    ? ["saz_catalog", "faculty_certificates"]
    : ["saz_catalog"];

  const message = run.error
    ? run.error.code === "SYNC_JOB_ALREADY_RUNNING"
      ? "Парсинг цього джерела вже виконується"
      : run.error.message
    : null;
  const list = jobs.data?.sync_jobs ?? [];

  return (
    <section aria-label="Синхронізація">
      <h1 className="font-display text-[22px]">Синхронізація</h1>
      <Card className="mt-4 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 font-medium">
          Джерело
          <select
            value={source}
            onChange={(event) => setSource(event.target.value as SyncSource)}
            className="rounded-[10px] border border-rule bg-surface px-3 py-2"
          >
            {sources.map((value) => (
              <option key={value} value={value}>
                {SOURCE_LABEL[value]}
              </option>
            ))}
          </select>
        </label>
        <Button
          disabled={run.isPending}
          onClick={() => run.mutate(source, { onSuccess: () => toast.success("Парсинг запущено") })}
        >
          Запустити парсинг
        </Button>
        {message && (
          <p role="alert" className="basis-full text-bad">
            {message}
          </p>
        )}
      </Card>

      <div className="relative mt-6 overflow-x-auto">
        {jobs.isError ? (
          <p role="alert" className="text-bad">
            Не вдалося завантажити журнал
          </p>
        ) : jobs.isSuccess && list.length === 0 ? (
          <p className="text-ink-2">Запусків ще не було</p>
        ) : (
          <table className="w-full min-w-[640px] border-collapse">
            <thead>
              <tr className="border-b border-rule text-ink-2">
                <th className={CELL}>Початок</th>
                <th className={CELL}>Джерело</th>
                <th className={CELL}>Ініціатор</th>
                <th className={CELL}>Статус</th>
                <th className={CELL}>Додано</th>
                <th className={CELL}>Оновлено</th>
                <th className={CELL}>Помилка</th>
              </tr>
            </thead>
            <tbody>
              {list.map((job) => (
                <tr
                  key={job.id}
                  className="border-b border-rule transition-colors duration-150 ease-out hover:bg-paper"
                >
                  <td className={CELL}>{formatDateTime(job.started_at)}</td>
                  <td className={CELL}>{SOURCE_LABEL[job.source]}</td>
                  <td className={CELL}>{job.initiated_by?.full_name ?? "Планувальник"}</td>
                  <td className={CELL}>
                    <Badge tone={STATUS_TONE[job.status]}>{syncStatusLabel(job.status)}</Badge>
                  </td>
                  <td className={CELL}>{job.added_count}</td>
                  <td className={CELL}>{job.updated_count}</td>
                  <td className={`${CELL} break-words text-bad`}>{job.error_message ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {jobs.data && (
        <Pagination
          page={page}
          pageSize={SYNC_PAGE_SIZE}
          total={jobs.data.pagination.total}
          onPage={setPage}
        />
      )}
    </section>
  );
}
