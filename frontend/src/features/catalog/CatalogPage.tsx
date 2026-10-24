// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: catalog-ui.test.tsx.
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { useConfig } from "../../api/config";
import { ApiError } from "../../api/errors";
import { Button } from "../../ui/Button";
import { CatalogFilters } from "./CatalogFilters";
import { DisciplineCard } from "./DisciplineCard";
import { Pagination } from "./Pagination";
import { PAGE_SIZE, filtersFromParams, paramsFromFilters, type DisciplineFilters } from "./filters";
import { useDebouncedValue } from "./useDebouncedValue";
import { useDirections, useDisciplines } from "./useDisciplines";

function SkeletonGrid() {
  return (
    <div aria-label="Завантажуємо каталог" aria-busy="true" className="grid gap-4 sm:grid-cols-2">
      {Array.from({ length: 6 }, (_, index) => (
        <div key={index} className="h-44 shimmer rounded-2xl bg-rule" />
      ))}
    </div>
  );
}

export function CatalogPage() {
  const [params, setParams] = useSearchParams();
  const { filters, page } = useMemo(() => filtersFromParams(params), [params]);
  const disciplines = useDisciplines(filters, page);
  const directions = useDirections();
  const config = useConfig();

  // Викладач вводиться текстом: оновлюємо адресу лише після паузи, щоб не слати запит на кожну літеру.
  const [instructor, setInstructor] = useState(filters.instructor ?? "");
  const debouncedInstructor = useDebouncedValue(instructor, 300);
  useEffect(() => {
    if (debouncedInstructor !== (filters.instructor ?? "")) {
      setParams(paramsFromFilters({ ...filters, instructor: debouncedInstructor || undefined }, 1));
    }
  }, [debouncedInstructor, filters, setParams]);

  function changeFilters(next: DisciplineFilters) {
    setParams(paramsFromFilters(next, 1));
  }
  function reset() {
    setInstructor("");
    setParams(new URLSearchParams());
  }

  const total = disciplines.data?.pagination.total ?? 0;
  const items = disciplines.data?.disciplines ?? [];

  let content;
  if (disciplines.isPending) {
    content = <SkeletonGrid />;
  } else if (disciplines.isError) {
    const error = disciplines.error;
    content = (
      <div role="alert" className="rounded-2xl bg-bad-bg p-5 text-bad">
        <p>{error instanceof ApiError ? error.message : "Не вдалося завантажити каталог"}</p>
        {error instanceof ApiError && error.requestId && (
          <p className="mt-1 text-sm">Код помилки: {error.requestId}</p>
        )}
        <Button
          variant="ghost"
          size="sm"
          className="mt-3"
          onClick={() => void disciplines.refetch()}
        >
          Спробувати ще раз
        </Button>
      </div>
    );
  } else if (items.length === 0) {
    content = (
      <div className="grid justify-items-center gap-3 rounded-2xl border-2 border-dashed border-rule p-10 text-center">
        <p className="font-display text-base">Нічого не знайдено</p>
        <p className="text-ink-2">Змініть фільтри або скиньте їх, щоб побачити всі дисципліни.</p>
        <Button onClick={reset}>Скинути фільтри</Button>
      </div>
    );
  } else {
    content = (
      <>
        <div className="grid gap-4 sm:grid-cols-2">
          {items.map((discipline, index) => (
            <DisciplineCard
              key={discipline.id}
              index={index}
              discipline={discipline}
              reviewsUrl={config.data?.reviews_url}
            />
          ))}
        </div>
        <Pagination
          page={page}
          pageSize={PAGE_SIZE}
          total={total}
          onPage={(next) => setParams(paramsFromFilters(filters, next))}
        />
      </>
    );
  }

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="font-display text-[22px]">Каталог вибіркових дисциплін</h1>
        {disciplines.data && <span className="text-ink-2">{total} дисциплін</span>}
      </div>
      <div className="grid items-start gap-5 lg:grid-cols-[1fr_270px]">
        <section aria-label="Дисципліни" className="min-w-0">
          {content}
        </section>
        <aside aria-label="Фільтри" className="order-first lg:sticky lg:top-4 lg:order-last">
          <CatalogFilters
            filters={filters}
            directions={directions.data?.directions ?? []}
            instructor={instructor}
            onInstructorChange={setInstructor}
            onChange={changeFilters}
            onReset={reset}
          />
        </aside>
      </div>
    </div>
  );
}
