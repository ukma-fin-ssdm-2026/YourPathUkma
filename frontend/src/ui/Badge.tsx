// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: ui.test.tsx.
import type { ReactNode } from "react";

export type PlanStatus = "draft" | "submitted" | "awaiting_deanery" | "approved";

type Tone = "neutral" | "info" | "warn" | "ok" | "bad";

const tones: Record<Tone, string> = {
  neutral: "bg-paper text-ink-2 ring-1 ring-inset ring-rule",
  info: "bg-info-bg text-cobalt",
  warn: "bg-warn-bg text-warn",
  ok: "bg-ok-bg text-ok",
  bad: "bg-bad-bg text-bad",
};

export function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

const statusView: Record<PlanStatus, { tone: Tone; label: string }> = {
  draft: { tone: "neutral", label: "Чернетка" },
  submitted: { tone: "info", label: "Подано" },
  awaiting_deanery: { tone: "warn", label: "Очікує деканату" },
  approved: { tone: "ok", label: "Затверджено" },
};

export function StatusBadge({ status }: { status: PlanStatus }) {
  const view = statusView[status];
  return <Badge tone={view.tone}>{view.label}</Badge>;
}
