// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: form.test.tsx.
import { useState } from "react";
import { toast } from "sonner";
import { useConfig } from "../../api/config";
import { fieldErrors } from "../../api/errors";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { useDirections } from "../catalog/useDisciplines";
import { useMe } from "../profile/useMe";
import { DirectionsField } from "./DirectionsField";
import { LoadField } from "./LoadField";
import { toggleDirection } from "./preferences";
import { usePreferences, useSavePreferences, type PreferencesInput } from "./usePreferences";

export function PreferencesForm({ year }: { year: number }) {
  const prefs = usePreferences(year);
  const directions = useDirections();
  const me = useMe();
  const config = useConfig();
  const save = useSavePreferences(year);

  // Чернетка з'являється після першої правки; до того показуємо збережене з сервера.
  const [draft, setDraft] = useState<PreferencesInput | null>(null);
  const [saved, setSaved] = useState(false);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [formErrors, setFormErrors] = useState<string[]>([]);

  const value = draft ?? prefs.data;
  if (prefs.isError) {
    return (
      <p role="alert" className="text-bad">
        Не вдалося завантажити побажання. Оновіть сторінку.
      </p>
    );
  }
  if (!value) {
    return (
      <p role="status" className="text-ink-2">
        Завантаження…
      </p>
    );
  }

  function edit(change: (current: PreferencesInput) => PreferencesInput) {
    setDraft(change(value!));
    setSaved(false);
  }

  function submit() {
    setFields({});
    setFormErrors([]);
    save.mutate(value!, {
      onSuccess: () => {
        setSaved(true);
        toast.success("Побажання збережено");
      },
      onError: (error) => {
        const parsed = fieldErrors(error.details);
        setFields(parsed.fields);
        setFormErrors(error.details.length === 0 ? [error.message] : parsed.form);
      },
    });
  }

  const levels = config.data?.load_levels;
  const hint = levels
    ? `Низьке — до ${levels.low.max_hours_per_week} годин на тиждень, середнє — ${levels.medium.min_hours_per_week}–${levels.medium.max_hours_per_week}, високе — ${levels.high.min_hours_per_week}–${levels.high.max_hours_per_week}.`
    : undefined;

  return (
    <div className="grid gap-4">
      <Card>
        <DirectionsField
          directions={directions.data?.directions ?? []}
          value={value.direction_ids}
          error={fields.direction_ids}
          onToggle={(id) => edit((c) => ({ ...c, direction_ids: toggleDirection(c.direction_ids, id) }))}
        />
      </Card>
      <Card>
        <LoadField
          value={value.load_levels}
          locked={me.data?.student?.load_levels_mode === "auto"}
          hint={hint}
          onChange={(season, level) =>
            edit((c) => ({ ...c, load_levels: { ...c.load_levels, [season]: level } }))
          }
        />
      </Card>
      {formErrors.map((message) => (
        <p key={message} role="alert" className="rounded-[10px] bg-bad-bg px-4 py-3 text-bad">
          {message}
        </p>
      ))}
      <div className="flex items-center gap-4">
        <Button disabled={save.isPending} onClick={submit}>
          Зберегти побажання
        </Button>
        {saved && (
          <p role="status" className="text-ok">
            Побажання збережено
          </p>
        )}
      </div>
    </div>
  );
}
