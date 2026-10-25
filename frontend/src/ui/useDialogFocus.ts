// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: ui.test.tsx.
import { type RefObject, useEffect } from "react";

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Модальний діалог: фокусує перший елемент панелі, тримає Tab/Shift+Tab у її межах,
 * закриває за Escape й повертає фокус на елемент, що відкрив діалог.
 */
export function useDialogFocus(
  panelRef: RefObject<HTMLElement | null>,
  onClose: () => void,
  active = true,
): void {
  useEffect(() => {
    if (!active) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const items = () =>
      Array.from(panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []);
    items()[0]?.focus();

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const list = items();
      if (list.length === 0) return;
      const first = list[0]!;
      const last = list[list.length - 1]!;
      const current = document.activeElement;
      if (event.shiftKey && (current === first || !panelRef.current?.contains(current))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (current === last || !panelRef.current?.contains(current))) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      opener?.focus();
    };
  }, [active, onClose, panelRef]);
}
