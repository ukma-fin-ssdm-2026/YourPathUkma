// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: summary.test.tsx, profile.test.tsx, npm run build.
import { useLayoutEffect, useRef } from "react";
import { formatCredits } from "../lib/credits";
import { canAnimate } from "./motion";

const DURATION_MS = 800;

/** Число, що «докручується» до нового значення. У jsdom і при prefers-reduced-motion показує значення одразу. */
export function CountUp({ value }: { value: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const shown = useRef(0);

  useLayoutEffect(() => {
    const el = ref.current;
    const from = shown.current;
    if (!el || !canAnimate() || from === value) {
      shown.current = value;
      return;
    }

    el.textContent = formatCredits(from);
    const start = performance.now();
    let frame = 0;
    const step = (now: number) => {
      const progress = Math.min(1, (now - start) / DURATION_MS);
      const eased = progress === 1 ? 1 : 1 - 2 ** (-10 * progress);
      shown.current = Math.round((from + (value - from) * eased) * 10) / 10;
      el.textContent = formatCredits(shown.current);
      if (progress < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [value]);

  return <span ref={ref}>{formatCredits(value)}</span>;
}
