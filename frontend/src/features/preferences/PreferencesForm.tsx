// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: form.test.tsx, instructors.test.tsx.
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { useConfig } from "../../api/config";
import { fieldErrors } from "../../api/errors";
import type { Instructor } from "../../api/types";
import { formatCredits } from "../../lib/credits";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { Switch } from "../../ui/Switch";
import { useDirections } from "../catalog/useDisciplines";
import { useMe } from "../profile/useMe";
import { DirectionsField } from "./DirectionsField";
import { InstructorPicker } from "./InstructorPicker";
import { LoadField } from "./LoadField";
import { moveInstructor, toggleDirection } from "./preferences";
import {
  useInstructorNames,
  usePreferences,
  useSavePreferences,
  type PreferencesInput,
} from "./usePreferences";

export function PreferencesForm({ year }: { year: number }) {
  const prefs = usePreferences(year);
  const directions = useDirections();
  const me = useMe();
  const config = useConfig();
  const save = useSavePreferences(year);
  const directoryNames = useInstructorNames();

  // Чернетка з'являється після першої правки; до того показуємо збережене з сервера.
  const [draft, setDraft] = useState<PreferencesInput | null>(null);
  const [saved, setSaved] = useState(false);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [formErrors, setFormErrors] = useState<string[]>([]);
  // Імена викладачів, знайдених пошуком (їх може не бути в першій сотні довідника).
  const [found, setFound] = useState<Map<number, string>>(new Map());
  const names = useMemo(() => new Map([...directoryNames, ...found]), [directoryNames, found]);

  // Чернетка належить конкретному року: після зміни року показуємо дані нового року.
  const value = draft?.academic_year === year ? draft : prefs.data;
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

  function addInstructor(to: "preferred" | "unwanted", instructor: Instructor) {
    setFound((current) => new Map(current).set(instructor.id, instructor.full_name));
    edit((c) => ({ ...c, ...moveInstructor(c, instructor.id, to) }));
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
  const credits = me.data?.student?.credits;
  const freeLeft = credits ? credits.free_choice_limit - credits.free_choice_used : null;
  const certificatesOn = config.data?.features.certificate_programs === true;

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
      <Card className="grid gap-3">
        <h2 className="font-display text-base">Викладачі</h2>
        <p className="text-ink-2">Список небажаних бачите лише ви.</p>
        {fields.preferred_instructor_ids && (
          <p role="alert" className="text-sm text-bad">
            {fields.preferred_instructor_ids}
          </p>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <InstructorPicker
            title="Бажані викладачі"
            searchLabel="Знайти викладача (бажані)"
            selectedIds={value.preferred_instructor_ids}
            otherIds={value.unwanted_instructor_ids}
            names={names}
            onAdd={(instructor) => addInstructor("preferred", instructor)}
            onRemove={(id) => edit((c) => ({ ...c, ...moveInstructor(c, id, null) }))}
          />
          <InstructorPicker
            title="Небажані викладачі"
            searchLabel="Знайти викладача (небажані)"
            selectedIds={value.unwanted_instructor_ids}
            otherIds={value.preferred_instructor_ids}
            names={names}
            onAdd={(instructor) => addInstructor("unwanted", instructor)}
            onRemove={(id) => edit((c) => ({ ...c, ...moveInstructor(c, id, null) }))}
          />
        </div>
      </Card>
      <Card className="divide-y divide-rule">
        <Switch
          label="Дозволити вільний вибір"
          description={
            freeLeft === null
              ? undefined
              : `Лишилось ${formatCredits(freeLeft)} з ${formatCredits(credits!.free_choice_limit)} кредитів на весь час навчання`
          }
          checked={value.include_free_electives}
          onChange={(checked) => edit((c) => ({ ...c, include_free_electives: checked }))}
        />
        <Switch
          label="Підібрати сертифікатну програму"
          description="Вмикається разом з AI-генерацією"
          badge={certificatesOn ? undefined : "незабаром"}
          checked={value.wants_certificate}
          disabled={!certificatesOn}
          onChange={(checked) => edit((c) => ({ ...c, wants_certificate: checked }))}
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
