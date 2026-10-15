// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: typecheck, ProfilePage і PlansPage тести.
/** Класи для посилання, що виглядає як основна кнопка. */
export const linkButtonClass =
  "inline-block rounded-[10px] bg-cobalt px-4 py-2.5 font-semibold text-on-accent transition-[transform,background-color] duration-150 ease-out hover:bg-cobalt-d active:scale-[.97] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt";

/** Те саме, але другорядне (контурне). */
export const linkGhostClass =
  "inline-block rounded-lg px-3 py-1.5 text-[13px] font-semibold text-ink ring-1 ring-inset ring-rule transition-[transform,background-color] duration-150 ease-out hover:bg-paper active:scale-[.97] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt";

/** Основна кнопка-посилання зменшеного розміру (для рядків таблиць). */
export const linkButtonSmClass = linkButtonClass.replace("rounded-[10px] px-4 py-2.5", "rounded-lg px-3 py-1.5 text-[13px]");
