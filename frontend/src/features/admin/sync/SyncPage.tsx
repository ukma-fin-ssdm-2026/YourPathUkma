// Використання ШІ: форми імпорту і віддаленого підключення за режимом додано Codex. Перевірка: Vitest.
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
  useImportSaz,
  useRunSync,
  useSyncJobs,
} from "./useSync";
import { toast } from "sonner";
import { RemoteSazLogin, useSazSession } from "./RemoteSazLogin";

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
  const upload = useImportSaz();
  const [file, setFile] = useState<File | null>(null);
  const liveEnabled = config.data?.features.saz_catalog_live === true;
  const remoteEnabled = liveEnabled && config.data?.features.saz_remote_login === true;
  const sazSession = useSazSession(remoteEnabled);
  const sources: SyncSource[] = liveEnabled ? ["saz_catalog"] : [];
  if (config.data?.features.certificate_programs) sources.push("faculty_certificates");
  const selectedSource = sources.includes(source) ? source : sources[0];

  const message = run.error
    ? run.error.code === "SYNC_JOB_ALREADY_RUNNING"
      ? "Парсинг цього джерела вже виконується"
      : run.error.message
    : null;
  const list = jobs.data?.sync_jobs ?? [];

  return (
    <section aria-label="Синхронізація">
      <h1 className="font-display text-[22px]">Синхронізація</h1>
      {remoteEnabled && <RemoteSazLogin connected={sazSession.data?.connected === true} />}
      {remoteEnabled && sazSession.error && <p role="alert" className="text-bad">{sazSession.error.message}</p>}
      {selectedSource && (
        <Card className="mt-4 flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 font-medium">
            Джерело
            <select
              value={selectedSource}
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
            disabled={
              run.isPending || (selectedSource === "saz_catalog" && remoteEnabled && !sazSession.data?.connected)
            }
            onClick={() => run.mutate(selectedSource, { onSuccess: () => toast.success("Парсинг запущено") })}
          >
            Запустити парсинг
          </Button>
          {message && (
            <p role="alert" className="basis-full text-bad">
              {message}
            </p>
          )}
        </Card>
      )}
      {config.isSuccess && !liveEnabled && (
        <form
          className="mt-4"
          onSubmit={(event) => {
            event.preventDefault();
            const form = event.currentTarget;
            if (file) {
              upload.mutate(file, {
                onSuccess: () => {
                  setFile(null);
                  form.reset();
                  toast.success("Каталог додано до черги модерації");
                },
              });
            }
          }}
        >
          <Card className="flex flex-wrap items-end gap-3">
            <p className="basis-full text-ink-2">
              Запустіть <code>python scripts/saz_export.py --bundle</code> на своєму комп’ютері та
              завантажте створений файл JSON із теки <code>saz_raw</code>.
            </p>
            <label className="flex flex-col gap-1 font-medium">
              Файл каталогу САЗ
              <input
                type="file"
                accept=".json,application/json"
                disabled={upload.isPending}
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </label>
            <Button type="submit" disabled={!file || upload.isPending}>
              Імпортувати каталог
            </Button>
            {upload.error && (
              <p role="alert" className="basis-full text-bad">
                {upload.error.message}
              </p>
            )}
          </Card>
        </form>
      )}

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
