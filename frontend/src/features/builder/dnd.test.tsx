// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
// Справжнє перетягування вказівником у jsdom не відтворити (нема геометрії), тож тестуємо чисту логіку
// рішень і обробники подій dnd-kit напряму, а розмітку звичайним рендером.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { CollisionDetection, DragEndEvent, DragStartEvent } from "@dnd-kit/core";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { server } from "../../mocks/server";
import { directionsHandler, disciplineFixture, disciplinesHandler } from "../../test/handlers";
import { CatalogPanel, CatalogRow } from "./CatalogPanel";
import {
  BuilderDnd,
  DraggableRow,
  DroppableColumn,
  columnState,
  decideDrop,
  makeDragHandlers,
  pointerFirst,
} from "./dnd";
import type { BuilderPlan } from "./plan";
import { TrimesterColumn } from "./TrimesterColumn";

const spring = disciplineFixture({ id: 5, title: "Машинне навчання", trimester: 2 });

describe("pointerFirst", () => {
  const rect = (left: number, width: number) => ({
    left,
    top: 0,
    width,
    height: 100,
    right: left + width,
    bottom: 100,
  });
  const container = (id: string) => ({
    id,
    data: { current: undefined },
    disabled: false,
    node: { current: null },
    rect: { current: null },
  });
  const args = (pointer: { x: number; y: number } | null) =>
    ({
      active: {
        id: "card",
        data: { current: undefined },
        rect: { current: { initial: null, translated: null } },
      },
      collisionRect: rect(90, 100),
      droppableRects: new Map([
        ["A", rect(0, 100)],
        ["B", rect(100, 100)],
      ]),
      droppableContainers: [container("A"), container("B")],
      pointerCoordinates: pointer,
    }) as unknown as Parameters<CollisionDetection>[0];

  it("обирає колонку під вказівником, а не ту, де більше площі картки", () => {
    expect(pointerFirst(args({ x: 50, y: 10 }))[0]?.id).toBe("A");
  });

  it("без вказівника (клавіатура) обирає за площею перетину", () => {
    expect(pointerFirst(args(null))[0]?.id).toBe("B");
  });
});

describe("decideDrop", () => {
  it("у свою колонку: додати", () => {
    expect(decideDrop(spring, 2)).toEqual({ kind: "add", discipline: spring, trimester: 2 });
  });
  it("у чужу колонку: відмова з поясненням", () => {
    expect(decideDrop(spring, 1)).toEqual({
      kind: "reject",
      message: "Ця дисципліна викладається навесні",
    });
  });
  it("поза колонками або без активної дисципліни: ігнорувати", () => {
    expect(decideDrop(spring, null)).toEqual({ kind: "ignore" });
    expect(decideDrop(null, 2)).toEqual({ kind: "ignore" });
  });
});

describe("columnState", () => {
  it("без перетягування колонка спокійна", () => {
    expect(columnState(null, 2, true)).toEqual({ over: false, hint: null });
  });
  it("над своєю колонкою підсвічується", () => {
    expect(columnState(spring, 2, true)).toEqual({ over: true, hint: null });
  });
  it("над чужою колонкою пояснює, чому не можна", () => {
    expect(columnState(spring, 1, true)).toEqual({
      over: false,
      hint: "Ця дисципліна викладається навесні",
    });
  });
  it("якщо курсор не над колонкою, підказки немає", () => {
    expect(columnState(spring, 1, false)).toEqual({ over: false, hint: null });
  });
});

describe("makeDragHandlers", () => {
  const start = (discipline = spring) =>
    ({ active: { data: { current: { discipline } } } }) as unknown as DragStartEvent;
  const end = (trimester: number | null, discipline = spring) =>
    ({
      active: { data: { current: { discipline } } },
      over: trimester === null ? null : { data: { current: { trimester } } },
    }) as unknown as DragEndEvent;

  function setup() {
    const calls = { active: [] as unknown[], message: [] as unknown[], dropped: [] as unknown[] };
    const handlers = makeDragHandlers({
      setActive: (value) => calls.active.push(value),
      setMessage: (value) => calls.message.push(value),
      onDropDiscipline: (d, t) => calls.dropped.push([d.id, t]),
    });
    return { calls, handlers };
  }

  it("початок перетягування запам'ятовує дисципліну й очищає повідомлення", () => {
    const { calls, handlers } = setup();
    handlers.onDragStart(start());
    expect(calls.active).toEqual([spring]);
    expect(calls.message).toEqual([null]);
  });

  it("drop у свою колонку додає дисципліну й скидає активну", () => {
    const { calls, handlers } = setup();
    handlers.onDragEnd(end(2));
    expect(calls.dropped).toEqual([[5, 2]]);
    expect(calls.active.at(-1)).toBeNull();
  });

  it("drop у чужу колонку не додає, а показує пояснення", () => {
    const { calls, handlers } = setup();
    handlers.onDragEnd(end(1));
    expect(calls.dropped).toEqual([]);
    expect(calls.message).toEqual(["Ця дисципліна викладається навесні"]);
  });

  it("drop поза колонками нічого не робить", () => {
    const { calls, handlers } = setup();
    handlers.onDragEnd(end(null));
    expect(calls.dropped).toEqual([]);
    expect(calls.message).toEqual([]);
    expect(calls.active.at(-1)).toBeNull();
  });

  it("скасування перетягування скидає активну дисципліну", () => {
    const { calls, handlers } = setup();
    handlers.onDragCancel();
    expect(calls.active).toEqual([null]);
  });
});

const plan: BuilderPlan = {
  academic_year: 2026,
  course: 3,
  load_levels: { autumn: "medium", spring: "medium", summer: "medium" },
  items: [],
};

describe("розмітка перетягування", () => {
  it("рядок має ручку з назвою, а «+» працює як і раніше", async () => {
    const onAdd = vi.fn();
    render(
      <BuilderDnd onDropDiscipline={() => {}}>
        <DraggableRow discipline={spring}>
          <CatalogRow discipline={spring} state="available" free={false} onAdd={onAdd} />
        </DraggableRow>
      </BuilderDnd>,
    );
    expect(
      screen.getByRole("button", { name: "Перетягнути Машинне навчання" }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Додати Машинне навчання" }));
    expect(onAdd).toHaveBeenCalledWith(spring);
  });

  it("колонка в DroppableColumn за замовчуванням не підсвічена й без підказки", () => {
    render(
      <BuilderDnd onDropDiscipline={() => {}}>
        <DroppableColumn trimester={2}>
          {(hint) => (
            <TrimesterColumn
              trimester={2}
              items={[]}
              normative={[]}
              load="medium"
              loadLocked={false}
              onLoadChange={() => {}}
              onRemove={() => {}}
              dropHint={hint}
            />
          )}
        </DroppableColumn>
      </BuilderDnd>,
    );
    expect(screen.getByRole("region", { name: "Весна" }).parentElement).toHaveAttribute(
      "data-over",
      "false",
    );
    expect(screen.getByText("Перетягніть дисципліну сюди")).toBeInTheDocument();
  });

  it("CatalogPanel з draggable малює ручки, а вимкнені рядки мають вимкнену ручку", async () => {
    server.use(
      directionsHandler([]),
      disciplinesHandler([
        spring,
        disciplineFixture({ id: 6, title: "Мова Haskell", trimester: 1 }),
      ]),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <BuilderDnd onDropDiscipline={() => {}}>
          <CatalogPanel
            plan={plan}
            studentDirections={[]}
            normativeIds={[6]}
            takenIds={[]}
            onAdd={() => {}}
            draggable
          />
        </BuilderDnd>
      </QueryClientProvider>,
    );
    expect(
      await screen.findByRole("button", { name: "Перетягнути Машинне навчання" }),
    ).toBeEnabled();
    expect(screen.getByRole("button", { name: "Перетягнути Мова Haskell" })).toBeDisabled();
  });
});
