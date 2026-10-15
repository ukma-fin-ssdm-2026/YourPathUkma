// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: upload.test.tsx, documents.test.tsx.
import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import { toast } from "sonner";
import { useConfig } from "../../api/config";
import { ApiError } from "../../api/errors";
import type { DeaneryDocument } from "../../api/types";
import { Card } from "../../ui/Card";
import { ConfirmDialog } from "../plans/ConfirmDialog";
import { defaultPlanYear } from "../profile/ProfilePage";
import { DocumentCard } from "./DocumentCard";
import { Dropzone } from "./Dropzone";
import { NormativePanel } from "./NormativePanel";
import {
  useDeaneryDocument,
  useDeaneryDocuments,
  useDeleteDocument,
  useUploadDocument,
} from "./useDeanery";

const DEFAULT_MAX_BYTES = 10_485_760;

function uploadMessage(error: ApiError): string {
  if (error.status === 413) return "Файл завеликий: максимум 10 МБ";
  if (error.status === 415) return "Підтримуються лише PDF і DOCX";
  if (error.status === 429) return "Забагато завантажень, спробуйте за кілька хвилин";
  return error.requestId ? `${error.message}. Код помилки: ${error.requestId}` : error.message;
}

function deleteMessage(error: ApiError): string {
  if (error.code === "DOCUMENT_IN_USE") return "Документ використовується в плані, який уже подано";
  if (error.status === 404) return "Документ не знайдено";
  return error.message;
}

export function DeaneryPage({ pollMs }: { pollMs?: number }) {
  const [params] = useSearchParams();
  const limits = useConfig().data?.limits;
  const year =
    Number(params.get("year")) ||
    defaultPlanYear(new Date(), limits?.academic_year_min ?? 2024, limits?.academic_year_max ?? 2030);

  const upload = useUploadDocument();
  const remove = useDeleteDocument();
  const documents = useDeaneryDocuments(year).data?.deanery_documents ?? [];
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [target, setTarget] = useState<DeaneryDocument | null>(null);

  // За замовчуванням у панелі найновіший розпізнаний документ.
  const latestParsed = [...documents].reverse().find((doc) => doc.parse_status === "parsed");
  const activeId = documents.some((doc) => doc.id === selectedId) ? selectedId : (latestParsed?.id ?? null);
  const active = useDeaneryDocument(activeId, { pollMs });
  const courses = active.data?.parse_status === "parsed" ? active.data.normative_courses : null;

  function handleFile(file: File) {
    setUploadError(null);
    setNotice(null);
    upload.mutate(
      { file, academicYear: year },
      {
        onSuccess: () => setNotice("Завантажено, розпізнаємо…"),
        onError: (error) => setUploadError(uploadMessage(error)),
      },
    );
  }

  function confirmDelete() {
    if (!target) return;
    remove.mutate(target.id, {
      onSuccess: () => {
        toast.success("Документ видалено");
        setTarget(null);
      },
      onError: (error) => {
        setDeleteError(deleteMessage(error));
        setTarget(null);
      },
    });
  }

  return (
    <div className="grid gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-[22px]">
          Документ деканату на {year}/{year + 1}
        </h1>
        <Link
          to="/path/create"
          className="rounded-[10px] px-4 py-2.5 font-semibold text-ink ring-1 ring-inset ring-rule transition-[transform,background-color] duration-150 ease-out hover:bg-surface active:scale-[.97] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt"
        >
          Пропустити зараз
        </Link>
      </div>

      <div className="grid items-start gap-5 lg:grid-cols-[1fr_320px]">
        <div className="grid gap-4">
          <Card>
            <h2 className="font-display text-base">Завантажте документ</h2>
            <p className="mt-1 mb-4 text-ink-2">
              Додайте файл від деканату з нормативними дисциплінами на цей рік. Так ви не оберете те,
              на що вас уже записали. PDF або DOCX, до 10 МБ.
            </p>
            <Dropzone
              maxBytes={limits?.max_upload_bytes ?? DEFAULT_MAX_BYTES}
              disabled={upload.isPending}
              onFile={handleFile}
              error={uploadError}
            />
            {notice && (
              <p role="status" className="mt-3 text-ok">
                {notice}
              </p>
            )}
          </Card>
          {deleteError && (
            <p role="alert" className="rounded-[10px] bg-bad-bg px-4 py-3 text-bad">
              {deleteError}
            </p>
          )}
          {documents.map((doc) => (
            <DocumentCard
              key={doc.id}
              doc={doc}
              selected={doc.id === activeId}
              pollMs={pollMs}
              onSelect={setSelectedId}
              onDelete={(item) => {
                setDeleteError(null);
                setTarget(item);
              }}
            />
          ))}
        </div>
        <NormativePanel courses={courses} year={year} />
      </div>

      <ConfirmDialog
        open={target !== null}
        title="Видалити документ?"
        description={target ? `Файл «${target.original_filename}» буде видалено.` : undefined}
        confirmLabel="Видалити"
        busy={remove.isPending}
        onConfirm={confirmDelete}
        onCancel={() => setTarget(null)}
      />
    </div>
  );
}
