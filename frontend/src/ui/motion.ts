// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: ui.test.tsx, columns.test.tsx.
import { useEffect, useState } from "react";

/** Чи можна програвати рух: у jsdom немає matchMedia, а при prefers-reduced-motion рух вимкнено. */
export function canAnimate(): boolean {
  return (
    typeof window.matchMedia === "function" &&
    !window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/**
 * Лишає елемент змонтованим ще `ms` після закриття, щоб відіграти анімацію виходу.
 * Без руху (тести, reduced-motion) зникає одразу.
 */
export function useExitTransition(open: boolean, ms = 150): { mounted: boolean; closing: boolean } {
  const [wasOpen, setWasOpen] = useState(open);
  const [lingering, setLingering] = useState(false);
  if (open !== wasOpen) {
    setWasOpen(open);
    setLingering(!open);
  }

  useEffect(() => {
    if (!lingering) return;
    const timer = window.setTimeout(() => setLingering(false), ms);
    return () => window.clearTimeout(timer);
  }, [lingering, ms]);

  const linger = lingering && canAnimate();
  return { mounted: open || linger, closing: !open && linger };
}
