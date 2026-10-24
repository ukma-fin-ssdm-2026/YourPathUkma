// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import css from "../styles/index.css?raw";
import { ConfirmDialog } from "../features/plans/ConfirmDialog";
import { Button } from "./Button";
import { StatusBadge, type PlanStatus } from "./Badge";
import { Segmented } from "./Segmented";

describe("Button", () => {
  it("викликає onClick", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Зберегти</Button>);
    await userEvent.click(screen.getByRole("button", { name: "Зберегти" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("не викликає onClick, коли disabled", async () => {
    const onClick = vi.fn();
    render(
      <Button onClick={onClick} disabled>
        Зберегти
      </Button>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Зберегти" }));
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe("StatusBadge", () => {
  const cases: [PlanStatus, string][] = [
    ["draft", "Чернетка"],
    ["submitted", "Подано"],
    ["awaiting_deanery", "Очікує деканату"],
    ["approved", "Затверджено"],
  ];
  it.each(cases)("статус %s має мітку «%s»", (status, label) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});

describe("Segmented", () => {
  const options = [
    { value: "low", label: "Низьке" },
    { value: "medium", label: "Середнє" },
  ];

  it("позначає активну кнопку й викликає onChange з новим значенням", async () => {
    const onChange = vi.fn();
    render(
      <Segmented value="low" options={options} onChange={onChange} ariaLabel="Навантаження" />,
    );
    expect(screen.getByRole("button", { name: "Низьке" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Середнє" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    await userEvent.click(screen.getByRole("button", { name: "Середнє" }));
    expect(onChange).toHaveBeenCalledWith("medium");
  });

  it("не реагує, коли disabled", async () => {
    const onChange = vi.fn();
    render(
      <Segmented
        value="low"
        options={options}
        onChange={onChange}
        ariaLabel="Навантаження"
        disabled
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Середнє" }));
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe("анімація діалогів", () => {
  it("ConfirmDialog має класи входу на підкладці й панелі", () => {
    render(
      <ConfirmDialog
        open
        title="Видалити?"
        confirmLabel="Видалити"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    const panel = screen.getByRole("dialog");
    expect(panel).toHaveClass("dialog-panel");
    expect(panel.parentElement).toHaveClass("dialog-backdrop");
  });

  it("кадри входу не стартують зі scale(0), тривалість до 300 мс, ease-out", () => {
    const block = /@keyframes dialog-in[\s\S]*?\n\}/.exec(css)?.[0] ?? "";
    expect(block).not.toBe("");
    expect(block).not.toMatch(/scale\(0\)/);
    expect(css).toMatch(
      /\.dialog-panel\s*{[^}]*animation:[^;]*(1[0-9]{2}|2[0-9]{2})ms var\(--ease-out\)/,
    );
  });

  it("для prefers-reduced-motion анімація діалогів вимкнена", () => {
    const reduced =
      /@media \(prefers-reduced-motion: reduce\)[\s\S]*?\r?\n\}\r?\n/.exec(css)?.[0] ?? "";
    expect(reduced).toMatch(/\.dialog-backdrop[\s\S]*animation:\s*none/);
  });
});

function DialogHarness() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>Відкрити</button>
      <ConfirmDialog
        open={open}
        title="Видалити?"
        confirmLabel="Видалити"
        onConfirm={() => {}}
        onCancel={() => setOpen(false)}
      />
    </>
  );
}

describe("фокус у діалозі", () => {
  it("переносить фокус у діалог, тримає Tab у його межах і повертає фокус після Escape", async () => {
    render(<DialogHarness />);
    const opener = screen.getByRole("button", { name: "Відкрити" });
    await userEvent.click(opener);
    const cancel = screen.getByRole("button", { name: "Скасувати" });
    const confirm = screen.getByRole("button", { name: "Видалити" });
    expect(cancel).toHaveFocus();

    await userEvent.tab();
    expect(confirm).toHaveFocus();
    await userEvent.tab();
    expect(cancel).toHaveFocus();
    await userEvent.tab({ shift: true });
    expect(confirm).toHaveFocus();

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });

  it("після скасування кнопкою фокус теж повертається", async () => {
    render(<DialogHarness />);
    const opener = screen.getByRole("button", { name: "Відкрити" });
    await userEvent.click(opener);
    await userEvent.click(screen.getByRole("button", { name: "Скасувати" }));
    expect(opener).toHaveFocus();
  });
});

describe("цілі дотику", () => {
  it("на touch-пристроях кнопки, посилання й поля мають висоту не менше 44px", () => {
    const block = /@media \(pointer: coarse\)[\s\S]*?\r?\n\}\r?\n/.exec(css)?.[0] ?? "";
    expect(block).toMatch(/min-height:\s*44px/);
    expect(block).toMatch(/button/);
    expect(block).toMatch(/a\[href\]/);
  });
});
