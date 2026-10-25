// Використання ШІ: тест створено за допомогою Claude (Anthropic). Перевірка: npx vitest run src/ui/motion.test.tsx.
import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConfirmDialog } from "../features/plans/ConfirmDialog";
import { PlanItemCard } from "../features/builder/PlanItemCard";
import type { PlanItem } from "../api/types";

function mockMotion(reduce: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: reduce && query.includes("reduce"),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const dialog = (open: boolean) => (
  <ConfirmDialog
    open={open}
    title="Видалити?"
    confirmLabel="Видалити"
    onConfirm={() => {}}
    onCancel={() => {}}
  />
);

describe("анімація виходу діалогу", () => {
  it("лишається ще 150 мс із класом is-closing, потім зникає", () => {
    mockMotion(false);
    vi.useFakeTimers();
    const { rerender } = render(dialog(true));
    rerender(dialog(false));
    expect(screen.getByRole("dialog")).toHaveClass("is-closing");
    act(() => {
      vi.advanceTimersByTime(160);
    });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("при prefers-reduced-motion зникає одразу", () => {
    mockMotion(true);
    const { rerender } = render(dialog(true));
    rerender(dialog(false));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

const item: PlanItem = {
  course_id: 7,
  title: "Етика ШІ",
  trimester: 3,
  credits: 3,
  is_free_elective: false,
};

describe("анімація видалення з плану", () => {
  it("картка відлітає, а дисципліна прибирається через 180 мс", () => {
    mockMotion(false);
    vi.useFakeTimers();
    const onRemove = vi.fn();
    render(<PlanItemCard item={item} onRemove={onRemove} />);
    act(() => screen.getByRole("button", { name: "Прибрати Етика ШІ" }).click());
    expect(screen.getByTestId("item-7")).toHaveClass("leave-out");
    expect(onRemove).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(190);
    });
    expect(onRemove).toHaveBeenCalledWith(7);
  });

  it("при prefers-reduced-motion прибирає одразу", () => {
    mockMotion(true);
    const onRemove = vi.fn();
    render(<PlanItemCard item={item} onRemove={onRemove} />);
    act(() => screen.getByRole("button", { name: "Прибрати Етика ШІ" }).click());
    expect(onRemove).toHaveBeenCalledWith(7);
  });
});
