// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: directions.test.tsx.
import { useState } from "react";
import { fieldErrors } from "../../../api/errors";
import type { Direction, DirectionInput } from "../../../api/types";
import { Button } from "../../../ui/Button";
import { Card } from "../../../ui/Card";
import { useSaveDirection } from "./useDirectionsAdmin";

const INPUT = "rounded-[10px] border border-rule bg-surface px-3 py-2 font-normal";

/** Створює напрямок або (з `direction`) редагує його, надсилаючи лише змінені поля. */
export function DirectionForm({ direction, onDone }: { direction?: Direction; onDone: () => void }) {
  const [name, setName] = useState(direction?.name ?? "");
  const [description, setDescription] = useState(direction?.description ?? "");
  const [clientError, setClientError] = useState<string | null>(null);
  const save = useSaveDirection();

  const submit = () => {
    const trimmed = name.trim();
    if (trimmed.length < 2 || trimmed.length > 50) {
      setClientError("Від 2 до 50 символів");
      return;
    }
    setClientError(null);
    const input: Partial<DirectionInput> = {};
    if (!direction || trimmed !== direction.name) input.name = trimmed;
    const text = description.trim();
    if (text !== (direction?.description ?? "")) input.description = text || (direction ? null : undefined);
    if (Object.keys(input).length === 0) {
      onDone();
      return;
    }
    save.mutate({ id: direction?.id, input }, { onSuccess: onDone });
  };

  const error = save.error;
  const server = error ? fieldErrors(error.details) : null;
  const nameError =
    clientError ??
    (error?.code === "DIRECTION_NAME_TAKEN" ? "Напрямок із такою назвою вже існує" : server?.fields.name);
  const formError =
    error && !nameError && !server?.fields.description ? [...(server?.form ?? []), error.message][0] : null;

  return (
    <Card className="mt-4 flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <label htmlFor="direction-name" className="font-medium">
          Назва
        </label>
        <input
          id="direction-name"
          value={name}
          aria-invalid={Boolean(nameError)}
          aria-describedby={nameError ? "direction-name-error" : undefined}
          onChange={(event) => setName(event.target.value)}
          className={INPUT}
        />
        {nameError && (
          <span id="direction-name-error" className="text-sm text-bad">
            {nameError}
          </span>
        )}
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="direction-description" className="font-medium">
          Опис
        </label>
        <input
          id="direction-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          className={INPUT}
        />
        {server?.fields.description && <span className="text-sm text-bad">{server.fields.description}</span>}
      </div>
      {formError && (
        <p role="alert" className="text-bad">
          {formError}
        </p>
      )}
      <div className="flex gap-2">
        <Button disabled={save.isPending} onClick={submit}>
          Зберегти
        </Button>
        <Button variant="ghost" onClick={onDone}>
          Скасувати
        </Button>
      </div>
    </Card>
  );
}
