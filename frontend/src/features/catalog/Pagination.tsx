// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: catalog-ui.test.tsx.
import { Button } from "../../ui/Button";

export function Pagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
}) {
  if (total === 0) return null;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = Math.min(total, (page - 1) * pageSize + 1);
  const to = Math.min(total, page * pageSize);
  return (
    <nav
      aria-label="Сторінки"
      className="flex items-center justify-between gap-3 pt-4 text-sm text-ink-2"
    >
      <span>
        {from}–{to} з {total}
      </span>
      <div className="flex items-center gap-2">
        <span>
          Сторінка {page} з {pages}
        </span>
        <Button variant="ghost" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Назад
        </Button>
        <Button variant="ghost" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Далі
        </Button>
      </div>
    </nav>
  );
}
