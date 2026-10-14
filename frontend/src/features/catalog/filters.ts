// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: catalog-data.test.tsx.
export const PAGE_SIZE = 12;

export interface DisciplineFilters {
  direction?: string;
  trimester?: 1 | 2 | 3;
  instructor?: string;
  min_credits?: number;
  max_credits?: number;
  recommended_year?: 2 | 3 | 4;
}

function oneOf<T extends number>(raw: string | null, allowed: readonly T[]): T | undefined {
  const value = Number(raw);
  return raw !== null && allowed.includes(value as T) ? (value as T) : undefined;
}

function credits(raw: string | null): number | undefined {
  if (raw === null || raw.trim() === "") return undefined;
  const value = Number(raw);
  return Number.isFinite(value) && value >= 0 ? value : undefined;
}

function text(raw: string | null): string | undefined {
  const value = raw?.trim();
  return value ? value : undefined;
}

/** Фільтри й номер сторінки живуть в адресі, тож посилання на каталог можна надіслати. */
export function filtersFromParams(params: URLSearchParams): { filters: DisciplineFilters; page: number } {
  const filters: DisciplineFilters = {};
  const direction = text(params.get("direction"));
  const instructor = text(params.get("instructor"));
  const trimester = oneOf(params.get("trimester"), [1, 2, 3] as const);
  const recommendedYear = oneOf(params.get("recommended_year"), [2, 3, 4] as const);
  const min = credits(params.get("min_credits"));
  const max = credits(params.get("max_credits"));
  if (direction) filters.direction = direction;
  if (trimester) filters.trimester = trimester;
  if (instructor) filters.instructor = instructor;
  if (min !== undefined) filters.min_credits = min;
  if (max !== undefined) filters.max_credits = max;
  if (recommendedYear) filters.recommended_year = recommendedYear;
  const page = Number(params.get("page"));
  return { filters, page: Number.isInteger(page) && page >= 1 ? page : 1 };
}

export function paramsFromFilters(filters: DisciplineFilters, page: number): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined) params.set(key, String(value));
  }
  if (page > 1) params.set("page", String(page));
  return params;
}

/** Query для GET /disciplines. Каталог показує лише вибіркові дисципліни. */
export function disciplinesQuery(
  filters: DisciplineFilters,
  page: number,
): Record<string, string | number> {
  const query: Record<string, string | number> = {
    discipline_type: "elective",
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  };
  if (filters.direction) query.direction = filters.direction;
  if (filters.trimester) query.trimester = filters.trimester;
  if (filters.recommended_year) query.recommended_year = filters.recommended_year;
  // Бекенд вимагає 2-100 символів для викладача й min <= max, інакше повертає 422.
  if (filters.instructor && filters.instructor.length >= 2) query.instructor = filters.instructor;
  const { min_credits: min, max_credits: max } = filters;
  const rangeIsValid = min === undefined || max === undefined || min <= max;
  if (rangeIsValid) {
    if (min !== undefined) query.min_credits = min;
    if (max !== undefined) query.max_credits = max;
  }
  return query;
}
