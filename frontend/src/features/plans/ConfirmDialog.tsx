// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: plans.test.tsx.
import { useRef } from "react";
import { Button } from "../../ui/Button";
import { useExitTransition } from "../../ui/motion";
import { useDialogFocus } from "../../ui/useDialogFocus";

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  busy = false,
  variant = "danger",
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel: string;
  busy?: boolean;
  variant?: "danger" | "primary";
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  useDialogFocus(panelRef, onCancel, open);
  const { mounted, closing } = useExitTransition(open);

  if (!mounted) return null;
  return (
    <div
      className={`dialog-backdrop fixed inset-0 z-10 grid place-items-center bg-black/40 p-4 ${closing ? "is-closing" : ""}`}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        className={`dialog-panel w-full max-w-sm rounded-2xl border border-rule bg-surface p-6 shadow-xl ${closing ? "is-closing" : ""}`}
      >
        <h2 id="confirm-title" className="font-display text-base">
          {title}
        </h2>
        {description && <p className="mt-2 text-ink-2">{description}</p>}
        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-[10px] px-4 py-2.5 font-semibold text-ink ring-1 ring-inset ring-rule transition-[transform,background-color] duration-150 ease-out hover:bg-paper active:scale-[.97] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cobalt"
          >
            Скасувати
          </button>
          <Button variant={variant} disabled={busy} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
