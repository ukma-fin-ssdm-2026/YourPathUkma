// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: directions.test.tsx.
import { useState } from "react";
import type { Direction } from "../../../api/types";
import { Button } from "../../../ui/Button";
import { Card } from "../../../ui/Card";
import { useDirections } from "../../catalog/useDisciplines";
import { ConfirmDialog } from "../../plans/ConfirmDialog";
import { DirectionForm } from "./DirectionForm";
import { useDeleteDirection } from "./useDirectionsAdmin";
import { toast } from "sonner";

type FormState = { mode: "create" } | { mode: "edit"; direction: Direction } | null;

export function DirectionsPage() {
  const directions = useDirections();
  const remove = useDeleteDirection();
  const [form, setForm] = useState<FormState>(null);
  const [deleting, setDeleting] = useState<Direction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const list = directions.data?.directions ?? [];

  const confirmDelete = () => {
    if (!deleting) return;
    setError(null);
    remove.mutate(deleting.id, {
      onSuccess: () => {
        setDeleting(null);
        toast.success("Напрямок видалено");
      },
      onError: (e) => {
        setDeleting(null);
        setError(
          e.code === "DIRECTION_IN_USE"
            ? "Напрямок використовується; спершу відв'яжіть його"
            : e.message,
        );
      },
    });
  };

  return (
    <section aria-label="Напрямки">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-[22px]">Напрямки</h1>
        {!form && <Button onClick={() => setForm({ mode: "create" })}>Додати напрямок</Button>}
      </div>

      {form && (
        <DirectionForm
          key={form.mode === "edit" ? form.direction.id : "new"}
          direction={form.mode === "edit" ? form.direction : undefined}
          onDone={() => setForm(null)}
        />
      )}
      {error && (
        <p role="alert" className="mt-4 text-bad">
          {error}
        </p>
      )}

      {directions.isError && (
        <p role="alert" className="mt-4 text-bad">
          Не вдалося завантажити напрямки
        </p>
      )}
      {directions.isSuccess && list.length === 0 && <p className="mt-4 text-ink-2">Напрямків ще немає</p>}
      <ul className="mt-4 space-y-3">
        {list.map((direction) => (
          <li key={direction.id} aria-label={direction.name}>
            <Card className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="font-medium break-words">{direction.name}</div>
                {direction.description && <div className="text-ink-2 break-words">{direction.description}</div>}
              </div>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={() => setForm({ mode: "edit", direction })}>
                  Редагувати
                </Button>
                <Button variant="danger" size="sm" onClick={() => setDeleting(direction)}>
                  Видалити
                </Button>
              </div>
            </Card>
          </li>
        ))}
      </ul>

      <ConfirmDialog
        open={deleting !== null}
        title={`Видалити напрямок «${deleting?.name ?? ""}»?`}
        description="Напрямок, прив'язаний до дисциплін або побажань, видалити не вийде."
        confirmLabel="Видалити"
        busy={remove.isPending}
        onConfirm={confirmDelete}
        onCancel={() => setDeleting(null)}
      />
    </section>
  );
}
