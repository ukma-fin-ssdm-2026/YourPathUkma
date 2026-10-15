// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: page.test.tsx.
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useConfig } from "../../api/config";
import { ApiError } from "../../api/errors";
import type { Discipline } from "../../api/types";
import { trimesterKey, type Trimester } from "../../lib/trimester";
import { Badge } from "../../ui/Badge";
import { linkGhostClass } from "../../ui/linkButton";
import { useDeaneryDocument, useDeaneryDocuments } from "../deanery/useDeanery";
import { useDirections } from "../catalog/useDisciplines";
import { usePreferences } from "../preferences/usePreferences";
import { defaultPlanYear } from "../profile/ProfilePage";
import { useAcademicHistory, useMe } from "../profile/useMe";
import { CatalogPanel } from "./CatalogPanel";
import { BuilderDnd, DroppableColumn } from "./dnd";
import {
  addDiscipline,
  blockMessage,
  canAdd,
  removeCourse,
  setLoad,
  trimesterOf,
  type BuilderPlan,
} from "./plan";
import { SummaryStrip } from "./SummaryStrip";
import { TrimesterColumn } from "./TrimesterColumn";
import { usePlan, useValidatePlan } from "./useBuilderData";

const EMPTY_PLAN: BuilderPlan = {
  academic_year: 2026,
  course: 3,
  load_levels: { autumn: "medium", spring: "medium", summer: "medium" },
  items: [],
};

function Notice({ children, action }: { children: string; action?: { to: string; label: string } }) {
  return (
    <div className="grid justify-items-start gap-3 rounded-2xl border border-rule bg-surface p-6">
      <p>{children}</p>
      {action && (
        <Link to={action.to} className={linkGhostClass}>
          {action.label}
        </Link>
      )}
    </div>
  );
}

export function BuilderPage() {
  const [params] = useSearchParams();
  const limits = useConfig().data?.limits;
  const year =
    Number(params.get("year")) ||
    defaultPlanYear(new Date(), limits?.academic_year_min ?? 2024, limits?.academic_year_max ?? 2030);
  const planId = Number(params.get("plan")) || null;

  const me = useMe();
  const prefs = usePreferences(year);
  const directions = useDirections();
  const history = useAcademicHistory();
  const planQuery = usePlan(planId);
  const documents = useDeaneryDocuments(year);
  const latestParsed = [...(documents.data?.deanery_documents ?? [])]
    .reverse()
    .find((doc) => doc.parse_status === "parsed");
  const document = useDeaneryDocument(latestParsed?.id ?? null);

  const student = me.data?.student ?? null;
  const normative = document.data?.parse_status === "parsed" ? document.data.normative_courses : [];

  // Початковий стан: збережена чернетка або порожній план із навантаженням із побажань.
  const base = useMemo<BuilderPlan | null>(() => {
    if (!student?.course_year || student.course_year < 2) return null;
    if (planId !== null) {
      const saved = planQuery.data;
      if (!saved) return null;
      return {
        academic_year: saved.academic_year,
        course: saved.course as 2 | 3 | 4,
        load_levels: {
          autumn: saved.load_levels.autumn ?? "medium",
          spring: saved.load_levels.spring ?? "medium",
          summer: saved.load_levels.summer ?? "medium",
        },
        items: saved.items,
      };
    }
    if (!prefs.data) return null;
    const levels = prefs.data.load_levels;
    return {
      academic_year: year,
      course: student.course_year as 2 | 3 | 4,
      load_levels: {
        autumn: levels.autumn ?? "medium",
        spring: levels.spring ?? "medium",
        summer: levels.summer ?? "medium",
      },
      items: [],
    };
  }, [student, planId, planQuery.data, prefs.data, year]);

  const [draft, setDraft] = useState<BuilderPlan | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const plan = draft ?? base;
  const validation = useValidatePlan(plan ?? EMPTY_PLAN);

  const studentDirections = (prefs.data?.direction_ids ?? [])
    .map((id) => directions.data?.directions.find((direction) => direction.id === id)?.name)
    .filter((name): name is string => Boolean(name));
  const takenIds = (history.data?.years ?? [])
    .flatMap((y) => y.records)
    .map((record) => record.course_id)
    .filter((id): id is number => id !== null);
  const normativeIds = normative.map((course) => course.course_id).filter((id): id is number => id !== null);

  if (me.isError) return <Notice>Не вдалося завантажити профіль. Оновіть сторінку.</Notice>;
  if (!me.data) {
    return (
      <p role="status" className="text-ink-2">
        Завантаження…
      </p>
    );
  }
  if (!student) return <Notice>Конструктор доступний лише студентам.</Notice>;
  if (!student.course_year || student.course_year < 2) {
    return (
      <Notice action={{ to: "/", label: "До профілю" }}>
        Для 1 курсу план формує деканат, тож у застосунку його не створити.
      </Notice>
    );
  }
  if (planId !== null && planQuery.isError) {
    const error = planQuery.error;
    const missing = error instanceof ApiError && (error.status === 404 || error.status === 403);
    return (
      <Notice action={{ to: "/path/saved", label: "Збережені плани" }}>
        {missing ? "План не знайдено" : error instanceof ApiError ? error.message : "Не вдалося завантажити план"}
      </Notice>
    );
  }
  if (planQuery.data && planQuery.data.status !== "draft") {
    return (
      <Notice action={{ to: "/path/saved", label: "Збережені плани" }}>
        Цей план уже подано, редагувати його не можна
      </Notice>
    );
  }
  if (!plan) {
    return (
      <p role="status" className="text-ink-2">
        Завантаження…
      </p>
    );
  }

  function handleAdd(discipline: Discipline) {
    const check = canAdd(plan!, discipline);
    if (!check.ok) {
      setNotice(blockMessage(check.reason));
      return;
    }
    setNotice(null);
    setDraft(addDiscipline(plan!, discipline, studentDirections));
  }

  const loadLocked = student.load_levels_mode === "auto";
  const normativeCredits = normative.reduce((sum, course) => sum + course.credits, 0);

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="flex flex-wrap items-center gap-3 font-display text-[22px]">
          План на {plan.academic_year}/{plan.academic_year + 1}
          <Badge tone="neutral">{planId !== null ? "Чернетка" : "Новий план"}</Badge>
        </h1>
        <div className="flex gap-2.5">
          <Link to={`/path/create/document?year=${year}`} className={linkGhostClass}>
            Документ деканату
          </Link>
          <Link to={`/path/create/preferences?year=${year}`} className={linkGhostClass}>
            Побажання
          </Link>
        </div>
      </div>

      <SummaryStrip
        plan={plan}
        validation={validation.data}
        credits={student.credits}
        normativeCredits={normativeCredits}
      />
      {notice && (
        <p role="status" className="rounded-[10px] bg-warn-bg px-4 py-2.5 text-warn">
          {notice}
        </p>
      )}

      <BuilderDnd onDropDiscipline={handleAdd}>
        <div className="grid items-start gap-4 lg:grid-cols-[1fr_360px]">
          <div className="grid gap-3 md:grid-cols-3">
            {([1, 2, 3] as Trimester[]).map((trimester) => (
              <DroppableColumn key={trimester} trimester={trimester}>
                {(hint) => (
                  <TrimesterColumn
                    trimester={trimester}
                    items={plan.items.filter((item) => trimesterOf(item) === trimester)}
                    normative={normative.filter((course) => course.trimester === trimester)}
                    load={plan.load_levels[trimesterKey(trimester)]}
                    loadLocked={loadLocked}
                    onLoadChange={(level) => setDraft(setLoad(plan, trimesterKey(trimester), level))}
                    onRemove={(courseId) => setDraft(removeCourse(plan, courseId))}
                    dropHint={hint}
                  />
                )}
              </DroppableColumn>
            ))}
          </div>
          <CatalogPanel
            plan={plan}
            studentDirections={studentDirections}
            normativeIds={normativeIds}
            takenIds={takenIds}
            onAdd={handleAdd}
            draggable
          />
        </div>
      </BuilderDnd>
    </div>
  );
}
