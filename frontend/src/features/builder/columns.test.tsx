// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { NormativeCourse, PlanItem } from "../../api/types";
import { PlanItemCard } from "./PlanItemCard";
import { NormativeCard, TrimesterColumn } from "./TrimesterColumn";

const item = (id: number, credits: number, free = false, title = `Дисципліна ${id}`): PlanItem => ({
  course_id: id,
  title,
  trimester: 1,
  credits,
  is_free_elective: free,
});
const normative: NormativeCourse = {
  course_id: 301,
  raw_title: "Архітектура ПЗ",
  trimester: 1,
  credits: 6,
};

function column(props: Partial<React.ComponentProps<typeof TrimesterColumn>> = {}) {
  const handlers = { onLoadChange: vi.fn(), onRemove: vi.fn() };
  render(
    <TrimesterColumn
      trimester={1}
      items={[item(1, 5), item(2, 3, true, "Управління продуктом")]}
      normative={[normative]}
      load="medium"
      loadLocked={false}
      {...handlers}
      {...props}
    />,
  );
  return handlers;
}

describe("PlanItemCard", () => {
  it("показує назву, кредити й тег вільного вибору", () => {
    render(<PlanItemCard item={item(2, 3, true, "Управління продуктом")} onRemove={() => {}} />);
    expect(screen.getByText("Управління продуктом")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("вільний вибір")).toBeInTheDocument();
  });

  it("не показує тег для профорієнтової дисципліни", () => {
    render(<PlanItemCard item={item(1, 5)} onRemove={() => {}} />);
    expect(screen.queryByText("вільний вибір")).not.toBeInTheDocument();
  });

  it("«Прибрати» викликає onRemove з course_id", async () => {
    const onRemove = vi.fn();
    render(<PlanItemCard item={item(7, 5, false, "Мова Haskell")} onRemove={onRemove} />);
    await userEvent.click(screen.getByRole("button", { name: "Прибрати Мова Haskell" }));
    expect(onRemove).toHaveBeenCalledWith(7);
  });

  it("помилка біля картки показується в alert", () => {
    render(<PlanItemCard item={item(1, 5)} error="У каталозі інші кредити" onRemove={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("У каталозі інші кредити");
  });
});

describe("NormativeCard", () => {
  it("показує дисципліну від деканату без кнопки видалення", () => {
    render(<NormativeCard course={normative} />);
    expect(screen.getByText("Архітектура ПЗ")).toBeInTheDocument();
    expect(screen.getByText("від деканату")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("TrimesterColumn", () => {
  it("рахує суму вибіркових і нормативних у заголовку", () => {
    column();
    expect(screen.getByRole("heading", { name: "Осінь" })).toBeInTheDocument();
    expect(screen.getByText("14 кр.")).toBeInTheDocument();
  });

  it("позначає колонку триместром", () => {
    column({ trimester: 2 });
    expect(screen.getByRole("region", { name: "Весна" })).toHaveAttribute("data-trimester", "2");
    expect(screen.getByRole("group", { name: "Навантаження: весна" })).toBeInTheDocument();
  });

  it("прибирання картки віддає course_id", async () => {
    const { onRemove } = column();
    await userEvent.click(screen.getByRole("button", { name: "Прибрати Дисципліна 1" }));
    expect(onRemove).toHaveBeenCalledWith(1);
  });

  it("нормативні лише для читання", () => {
    column();
    expect(screen.getByText("від деканату")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Прибрати Архітектура ПЗ" }),
    ).not.toBeInTheDocument();
  });

  it("зміна навантаження віддає рівень, а при loadLocked перемикач недоступний", async () => {
    const { onLoadChange } = column();
    await userEvent.click(
      within(screen.getByRole("group", { name: "Навантаження: осінь" })).getByRole("button", {
        name: "Високе",
      }),
    );
    expect(onLoadChange).toHaveBeenCalledWith("high");
  });

  it("при loadLocked перемикач навантаження недоступний", () => {
    column({ loadLocked: true });
    for (const button of within(
      screen.getByRole("group", { name: "Навантаження: осінь" }),
    ).getAllByRole("button")) {
      expect(button).toBeDisabled();
    }
  });

  it("порожня колонка показує слот для перетягування", () => {
    column({ items: [], normative: [] });
    expect(screen.getByText("Перетягніть дисципліну сюди")).toBeInTheDocument();
    expect(screen.getByText("0 кр.")).toBeInTheDocument();
  });

  it("підказка dropHint замінює слот і читається зі статусу", () => {
    column({ dropHint: "Ця дисципліна викладається навесні" });
    expect(screen.getByRole("status")).toHaveTextContent("Ця дисципліна викладається навесні");
    expect(screen.queryByText("Перетягніть дисципліну сюди")).not.toBeInTheDocument();
  });

  it("помилки елементів показуються біля відповідних карток", () => {
    column({ itemErrors: { 2: "У каталозі інші кредити" } });
    const card = screen.getByTestId("item-2");
    expect(within(card).getByRole("alert")).toHaveTextContent("У каталозі інші кредити");
  });
});
