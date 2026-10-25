// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: auth-ui.test.tsx, ручний запуск dev.
import type { CSSProperties, ReactNode } from "react";

// Декоративна смуга кредитів: нормативні, профорієнтовні, вільний вибір, порожні.
const CELLS: string[] = [
  ...Array<string>(30).fill("bg-[#8e99b8]"),
  ...Array<string>(14).fill("bg-[#8ca2ec]"),
  ...Array<string>(6).fill("bg-[#a797e6]"),
  ...Array<string>(22).fill("bg-on-hero/15"),
];

/** Широкий екран входу й онбордингу: темна панель зліва, форма справа. */
export function AuthShell({
  heading,
  lead,
  showLedger = false,
  children,
}: {
  heading: string;
  lead: string;
  showLedger?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto my-6 grid min-h-[640px] max-w-[1280px] overflow-hidden rounded-3xl border border-rule bg-surface md:grid-cols-[1.15fr_1fr]">
      <section className="flex flex-col bg-hero p-8 text-on-hero md:p-14">
        <div className="flex items-center gap-3 font-display text-xl font-semibold">
          <span aria-hidden="true" className="size-[34px] rounded-[10px] bg-cobalt" />
          YourPath
        </div>
        <h1
          className="rise mt-16 mb-4 max-w-[14ch] font-display text-3xl leading-tight md:mt-auto md:text-[40px]"
          style={{ "--i": 1 } as CSSProperties}
        >
          {heading}
        </h1>
        <p className="rise max-w-[34ch] text-lg opacity-80" style={{ "--i": 2 } as CSSProperties}>
          {lead}
        </p>
        {showLedger && (
          <div
            aria-hidden="true"
            className="mt-10 grid max-w-[520px] grid-cols-[repeat(24,1fr)] gap-1"
          >
            {CELLS.map((tone, index) => (
              <i
                key={index}
                className={`cell-in block aspect-square rounded-[3px] ${tone}`}
                style={{ "--i": index, "--row": 2 } as CSSProperties}
              />
            ))}
          </div>
        )}
      </section>
      <section
        className="rise flex flex-col justify-center p-8 md:p-14"
        style={{ "--i": 2 } as CSSProperties}
      >
        {children}
      </section>
    </div>
  );
}
