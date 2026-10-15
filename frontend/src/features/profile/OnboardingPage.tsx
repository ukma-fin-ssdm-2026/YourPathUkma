// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: onboarding.test.tsx.
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router";
import { fieldErrors } from "../../api/errors";
import { AuthShell } from "../../auth/AuthShell";
import { Button } from "../../ui/Button";
import { Segmented } from "../../ui/Segmented";
import { useMe, useOnboard } from "./useMe";

const COURSES = [1, 2, 3, 4].map((value) => ({ value, label: String(value) }));
const inputClass =
  "w-full rounded-[10px] border border-rule bg-paper px-4 py-3.5 text-base text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt";

export function OnboardingPage() {
  const me = useMe();
  const onboard = useOnboard();
  const navigate = useNavigate();
  const [course, setCourse] = useState(0);
  const [specialty, setSpecialty] = useState("");
  const [courseError, setCourseError] = useState(false);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [formErrors, setFormErrors] = useState<string[]>([]);

  if (me.data?.student && !me.data.student.onboarding_required) return <Navigate to="/" replace />;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (course === 0) {
      setCourseError(true);
      return;
    }
    setCourseError(false);
    onboard.mutate(
      { course_year: course as 1 | 2 | 3 | 4, specialty: specialty.trim() },
      {
        onSuccess: () => navigate("/", { replace: true }),
        onError: (error) => {
          if (error.code === "ALREADY_ONBOARDED") {
            navigate("/", { replace: true });
            return;
          }
          const parsed = fieldErrors(error.details);
          setFields(parsed.fields);
          setFormErrors(error.details.length === 0 ? [error.message] : parsed.form);
        },
      },
    );
  }

  return (
    <AuthShell
      heading="Давайте налаштуємо ваш профіль"
      lead="Це займе хвилину. Від курсу залежить, як ми розрахуємо навантаження й що вам доступно."
    >
      <form onSubmit={submit} noValidate className="max-w-[420px]">
        <h2 className="mb-2 font-display text-[28px] leading-tight">Розкажіть про себе</h2>
        <p className="mb-8 text-[17px] text-ink-2">
          Заповнюється один раз. Змінити курс згодом може лише адміністратор.
        </p>

        <div className="mb-5 grid gap-1.5">
          <span className="font-semibold">На якому ви курсі?</span>
          <Segmented
            value={course}
            options={COURSES}
            onChange={(value) => {
              setCourse(value);
              setCourseError(false);
            }}
            ariaLabel="Курс"
          />
          {course === 1 && (
            <small className="text-sm text-ink-2">
              Для 1 курсу план формує деканат, тож у застосунку його не створити.
            </small>
          )}
          {courseError && (
            <small role="alert" className="text-sm text-bad">
              Оберіть курс
            </small>
          )}
        </div>

        <div className="mb-6 grid gap-1.5">
          <label htmlFor="specialty" className="font-semibold">
            Спеціальність
          </label>
          <input
            id="specialty"
            className={inputClass}
            value={specialty}
            onChange={(event) => setSpecialty(event.target.value)}
            aria-invalid={fields.specialty ? true : undefined}
          />
          {fields.specialty && (
            <small role="alert" className="text-sm text-bad">
              {fields.specialty}
            </small>
          )}
        </div>

        {fields.course_year && (
          <p role="alert" className="mb-4 text-sm text-bad">
            {fields.course_year}
          </p>
        )}
        {formErrors.map((message) => (
          <p key={message} role="alert" className="mb-4 text-sm text-bad">
            {message}
          </p>
        ))}

        <Button type="submit" disabled={onboard.isPending} className="w-full py-3.5 text-[17px]">
          Продовжити
        </Button>
      </form>
    </AuthShell>
  );
}
