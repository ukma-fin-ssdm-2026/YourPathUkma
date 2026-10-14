// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: instructors.test.tsx.
import { Link, useSearchParams } from "react-router";
import { useConfig } from "../../api/config";
import { defaultPlanYear } from "../profile/ProfilePage";
import { PreferencesForm } from "./PreferencesForm";

export function PreferencesPage() {
  const [params] = useSearchParams();
  const limits = useConfig().data?.limits;
  const year =
    Number(params.get("year")) ||
    defaultPlanYear(new Date(), limits?.academic_year_min ?? 2024, limits?.academic_year_max ?? 2030);
  return (
    <div className="grid gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-[22px]">
          Побажання на {year}/{year + 1}
        </h1>
        <div className="flex gap-2.5">
          <Link
            to={`/path/create/document?year=${year}`}
            className="rounded-[10px] px-4 py-2.5 font-semibold text-ink ring-1 ring-inset ring-rule transition-[transform,background-color] duration-150 ease-out hover:bg-surface active:scale-[.97] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt"
          >
            Назад до документа
          </Link>
          <Link
            to="/path/create"
            className="rounded-[10px] px-4 py-2.5 font-semibold text-ink ring-1 ring-inset ring-rule transition-[transform,background-color] duration-150 ease-out hover:bg-surface active:scale-[.97] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt"
          >
            До конструктора
          </Link>
        </div>
      </div>
      <PreferencesForm year={year} />
    </div>
  );
}
