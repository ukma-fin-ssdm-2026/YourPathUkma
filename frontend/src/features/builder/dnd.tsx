// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: dnd.test.tsx.
// Перетягування дисципліни з каталогу у власну колонку. Запасний шлях для клавіатури й телефону кнопка «+».
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { createContext, useContext, useState, type ReactNode } from "react";
import type { Discipline } from "../../api/types";
import type { Trimester } from "../../lib/trimester";
import { dropVerdict } from "./plan";

export type DropDecision =
  | { kind: "add"; discipline: Discipline; trimester: Trimester }
  | { kind: "reject"; message: string }
  | { kind: "ignore" };

export function decideDrop(discipline: Discipline | null, trimester: Trimester | null): DropDecision {
  if (!discipline || trimester === null) return { kind: "ignore" };
  const verdict = dropVerdict(discipline, trimester);
  return verdict.ok ? { kind: "add", discipline, trimester } : { kind: "reject", message: verdict.message };
}

/** Як виглядає колонка під час перетягування: підсвічена, якщо підходить, або з поясненням, якщо ні. */
export function columnState(
  active: Discipline | null,
  column: Trimester,
  isOver: boolean,
): { over: boolean; hint: string | null } {
  if (!active || !isOver) return { over: false, hint: null };
  const verdict = dropVerdict(active, column);
  return verdict.ok ? { over: true, hint: null } : { over: false, hint: verdict.message };
}

export function makeDragHandlers(deps: {
  setActive: (discipline: Discipline | null) => void;
  setMessage: (message: string | null) => void;
  onDropDiscipline: (discipline: Discipline, trimester: Trimester) => void;
}) {
  return {
    onDragStart(event: DragStartEvent) {
      deps.setMessage(null);
      deps.setActive((event.active.data.current?.discipline as Discipline | undefined) ?? null);
    },
    onDragEnd(event: DragEndEvent) {
      const discipline = (event.active.data.current?.discipline as Discipline | undefined) ?? null;
      const trimester = (event.over?.data.current?.trimester as Trimester | undefined) ?? null;
      deps.setActive(null);
      const decision = decideDrop(discipline, trimester);
      if (decision.kind === "add") deps.onDropDiscipline(decision.discipline, decision.trimester);
      if (decision.kind === "reject") deps.setMessage(decision.message);
    },
    onDragCancel() {
      deps.setActive(null);
    },
  };
}

const ActiveContext = createContext<Discipline | null>(null);
export const useActiveDiscipline = () => useContext(ActiveContext);

export function BuilderDnd({
  onDropDiscipline,
  children,
}: {
  onDropDiscipline: (discipline: Discipline, trimester: Trimester) => void;
  children: ReactNode;
}) {
  const [active, setActive] = useState<Discipline | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  );
  const handlers = makeDragHandlers({ setActive, setMessage, onDropDiscipline });
  return (
    <DndContext sensors={sensors} {...handlers}>
      <ActiveContext.Provider value={active}>
        {message && (
          <p role="status" className="mb-3 rounded-[10px] bg-warn-bg px-4 py-2.5 text-warn">
            {message}
          </p>
        )}
        {children}
      </ActiveContext.Provider>
    </DndContext>
  );
}

export function DraggableRow({
  discipline,
  disabled = false,
  children,
}: {
  discipline: Discipline;
  disabled?: boolean;
  children: ReactNode;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `discipline-${discipline.id}`,
    data: { discipline },
    disabled,
  });
  const style = transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : undefined;
  return (
    <div ref={setNodeRef} style={style} className={isDragging ? "relative z-10 opacity-90 shadow-lg" : ""}>
      <div className="flex items-stretch gap-1">
        <button
          type="button"
          aria-label={`Перетягнути ${discipline.title}`}
          disabled={disabled}
          {...attributes}
          {...listeners}
          className="cursor-grab touch-none px-1 text-ink-2 focus-visible:outline-2 focus-visible:outline-cobalt disabled:cursor-not-allowed disabled:opacity-40"
        >
          ⋮⋮
        </button>
        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </div>
  );
}

export function DroppableColumn({
  trimester,
  children,
}: {
  trimester: Trimester;
  children: (hint: string | null) => ReactNode;
}) {
  const active = useActiveDiscipline();
  const { setNodeRef, isOver } = useDroppable({ id: `column-${trimester}`, data: { trimester } });
  const { over, hint } = columnState(active, trimester, isOver);
  return (
    <div
      ref={setNodeRef}
      data-over={over}
      className={"rounded-2xl transition-shadow duration-150 ease-out " + (over ? "ring-2 ring-cobalt" : "")}
    >
      {children(hint)}
    </div>
  );
}
