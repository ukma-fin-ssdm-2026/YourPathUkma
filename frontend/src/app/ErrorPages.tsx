// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: ErrorPages.test.tsx.
import { Link } from "react-router";

function Screen({ title, text }: { title: string; text: string }) {
  return (
    <main className="grid min-h-screen place-items-center bg-paper px-4 text-ink">
      <div className="max-w-md text-center">
        <h1 className="font-display text-[26px]">{title}</h1>
        <p className="mt-3 text-ink-2">{text}</p>
        <Link
          to="/"
          className="mt-6 inline-block rounded-[10px] bg-cobalt px-5 py-2.5 font-semibold text-on-accent transition-transform duration-150 ease-out active:scale-[.97] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt"
        >
          На головну
        </Link>
      </div>
    </main>
  );
}

export const NotFoundPage = () => (
  <Screen
    title="Сторінку не знайдено"
    text="Можливо, посилання застаріло або в адресі є помилка."
  />
);

/** Показується, коли екран упав з помилкою; замість англомовного екрана за замовчуванням. */
export const RouteErrorPage = () => (
  <Screen title="Щось пішло не так" text="Спробуйте оновити сторінку або повернутися на головну." />
);
