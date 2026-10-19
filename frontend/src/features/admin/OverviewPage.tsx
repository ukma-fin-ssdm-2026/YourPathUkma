// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: admin.test.tsx.
import type { CSSProperties } from "react";
import { Link } from "react-router";
import { Card } from "../../ui/Card";

const CARDS = [
  { to: "/admin/moderation", title: "Модерація", text: "Зміни каталогу, які чекають на рішення." },
  { to: "/admin/sync", title: "Синхронізація", text: "Запуск парсингу й журнал запусків." },
  { to: "/admin/users", title: "Користувачі", text: "Ролі, курс і спеціальність студентів." },
  { to: "/admin/directions", title: "Напрямки", text: "Довідник напрямків для побажань." },
  { to: "/admin/audit", title: "Журнал дій", text: "Хто й що переглядав та змінював." },
];

export function OverviewPage() {
  return (
    <section aria-label="Огляд адмінки">
      <h1 className="font-display text-[22px]">Адмінка</h1>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        {CARDS.map((card, index) => (
          <Link
            key={card.to}
            to={card.to}
            className="rise rounded-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt"
            style={{ "--i": index } as CSSProperties}
          >
            <Card className="h-full transition-[translate,border-color,box-shadow] duration-200 ease-out hover:-translate-y-1 hover:border-cobalt hover:shadow-lg">
              <h2 className="font-display text-[16px]">{card.title}</h2>
              <p className="mt-1 text-ink-2">{card.text}</p>
            </Card>
          </Link>
        ))}
      </div>
    </section>
  );
}
