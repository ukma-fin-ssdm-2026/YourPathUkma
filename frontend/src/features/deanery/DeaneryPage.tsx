// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: upload.test.tsx.
import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useConfig } from "../../api/config";
import { ApiError } from "../../api/errors";
import { defaultPlanYear } from "../profile/ProfilePage";
import { Card } from "../../ui/Card";
import { Dropzone } from "./Dropzone";
import { useUploadDocument } from "./useDeanery";

const DEFAULT_MAX_BYTES = 10_485_760;

function uploadMessage(error: ApiError): string {
  if (error.status === 413) return "Файл завеликий: максимум 10 МБ";
  if (error.status === 415) return "Підтримуються лише PDF і DOCX";
  if (error.status === 429) return "Забагато завантажень, спробуйте за кілька хвилин";
  return error.requestId ? `${error.message}. Код помилки: ${error.requestId}` : error.message;
}

export function DeaneryPage() {
  const [params] = useSearchParams();
  const limits = useConfig().data?.limits;
  const year =
    Number(params.get("year")) ||
    defaultPlanYear(new Date(), limits?.academic_year_min ?? 2024, limits?.academic_year_max ?? 2030);
  const upload = useUploadDocument();
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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
      <Card>
        <h2 className="font-display text-base">Завантажте документ</h2>
        <p className="mt-1 mb-4 text-ink-2">
          Додайте файл від деканату з нормативними дисциплінами на цей рік. Так ви не оберете те, на що
          вас уже записали. PDF або DOCX, до 10 МБ.
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
    </div>
  );
}
