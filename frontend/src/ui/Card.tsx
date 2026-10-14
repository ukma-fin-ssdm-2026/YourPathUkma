// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm run typecheck, lint.
import type { HTMLAttributes } from "react";

export function Card({ className = "", ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`rounded-2xl border border-rule bg-surface p-5 ${className}`} {...rest} />;
}
