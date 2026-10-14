// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: upload.test.tsx.
import { useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { Button } from "../../ui/Button";
import { validateDeaneryFile } from "./validateFile";

export function Dropzone({
  maxBytes,
  disabled = false,
  onFile,
  error,
}: {
  maxBytes: number;
  disabled?: boolean;
  onFile: (file: File) => void;
  error?: string | null;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  function accept(file: File | undefined) {
    if (!file || disabled) return;
    const problem = validateDeaneryFile(file, maxBytes);
    setLocalError(problem);
    if (!problem) onFile(file);
  }

  function onDrag(event: DragEvent, value: boolean) {
    event.preventDefault();
    setDragging(value);
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    accept(event.dataTransfer.files[0]);
  }

  function onChange(event: ChangeEvent<HTMLInputElement>) {
    accept(event.target.files?.[0]);
    event.target.value = ""; // дозволяє вибрати той самий файл ще раз
  }

  const message = localError ?? error ?? null;
  return (
    <div>
      <div
        data-testid="dropzone"
        data-dragging={dragging}
        onDragEnter={(event) => onDrag(event, true)}
        onDragOver={(event) => onDrag(event, true)}
        onDragLeave={(event) => onDrag(event, false)}
        onDrop={onDrop}
        className={
          "grid justify-items-center gap-2 rounded-2xl border-2 border-dashed px-5 py-9 text-center transition-[background-color,border-color] duration-200 ease-out " +
          (dragging ? "border-cobalt bg-info-bg" : "border-rule bg-paper")
        }
      >
        <b className="text-base">Перетягніть файл сюди</b>
        <span className="text-ink-2">або</span>
        <Button size="sm" disabled={disabled} onClick={() => inputRef.current?.click()}>
          Обрати файл
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          aria-label="Файл документа деканату"
          className="sr-only"
          tabIndex={-1}
          disabled={disabled}
          onChange={onChange}
        />
      </div>
      {message && (
        <p role="alert" className="mt-3 rounded-[10px] bg-bad-bg px-4 py-3 text-bad">
          {message}
        </p>
      )}
    </div>
  );
}
