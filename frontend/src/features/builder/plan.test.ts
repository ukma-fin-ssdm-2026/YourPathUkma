// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import type { PlanItem } from "../../api/types";
import { disciplineFixture } from "../../test/handlers";
import {
  FREE_LIMIT,
  MAX_ITEMS,
  addDiscipline,
  blockMessage,
  canAdd,
  dropVerdict,
  isFreeElective,
  removeCourse,
  setLoad,
  summarize,
  toPlanItem,
  type BuilderPlan,
} from "./plan";

const emptyPlan = (): BuilderPlan => ({
  academic_year: 2026,
  course: 3,
  load_levels: { autumn: "medium", spring: "medium", summer: "medium" },
  items: [],
});

const item = (id: number, trimester: 1 | 2 | 3, credits: number, free = false): PlanItem => ({
  course_id: id,
  title: `Дисципліна ${id}`,
  trimester,
  credits,
  is_free_elective: free,
});

describe("isFreeElective", () => {
  it("порожні напрямки дисципліни означають вільний вибір", () => {
    expect(isFreeElective(disciplineFixture({ directions: [] }), ["Data Science"])).toBe(true);
  });
  it("збіг напрямку студента (без урахування регістру) дає профорієнтовну", () => {
    expect(isFreeElective(disciplineFixture({ directions: ["Data Science"] }), ["data science"])).toBe(false);
  });
  it("без збігу напрямків це вільний вибір", () => {
    expect(isFreeElective(disciplineFixture({ directions: ["Data Science"] }), ["Cybersecurity"])).toBe(true);
  });
  it("якщо студент не обрав напрямків, дисципліна з напрямками вважається вільним вибором", () => {
    expect(isFreeElective(disciplineFixture({ directions: ["Data Science"] }), [])).toBe(true);
  });
});

describe("toPlanItem", () => {
  it("копіює дані дисципліни й ставить прапорець вільного вибору", () => {
    const d = disciplineFixture({ id: 205, title: "Управління продуктом", trimester: 2, credits: 3, directions: [] });
    expect(toPlanItem(d, [])).toEqual({
      course_id: 205,
      title: "Управління продуктом",
      trimester: 2,
      credits: 3,
      is_free_elective: true,
    });
  });
});

describe("canAdd / addDiscipline", () => {
  it("додає дисципліну, але не дубль", () => {
    const d = disciplineFixture({ id: 101 });
    const once = addDiscipline(emptyPlan(), d, ["Software Engineering"]);
    expect(once.items).toHaveLength(1);
    expect(canAdd(once, d)).toEqual({ ok: false, reason: "duplicate" });
    expect(addDiscipline(once, d, [])).toBe(once);
  });

  it("не додає 31-шу дисципліну", () => {
    const plan = { ...emptyPlan(), items: Array.from({ length: MAX_ITEMS }, (_, i) => item(i + 1, 1, 1)) };
    expect(canAdd(plan, disciplineFixture({ id: 999 }))).toEqual({ ok: false, reason: "limit" });
  });

  it("не додає нормативну дисципліну", () => {
    expect(canAdd(emptyPlan(), disciplineFixture({ discipline_type: "normative" }))).toEqual({
      ok: false,
      reason: "normative",
    });
  });

  it("повідомлення для кожної причини відмови", () => {
    expect(blockMessage("duplicate")).toBe("Ця дисципліна вже в плані");
    expect(blockMessage("limit")).toBe("У плані може бути не більше 30 дисциплін");
    expect(blockMessage("normative")).toBe("Нормативні дисципліни додає деканат");
  });
});

describe("removeCourse / setLoad", () => {
  it("removeCourse прибирає за course_id і не чіпає решту", () => {
    const plan = { ...emptyPlan(), items: [item(1, 1, 5), item(2, 2, 3)] };
    expect(removeCourse(plan, 1).items.map((i) => i.course_id)).toEqual([2]);
  });
  it("setLoad змінює лише вказаний сезон", () => {
    expect(setLoad(emptyPlan(), "summer", "low").load_levels).toEqual({
      autumn: "medium",
      spring: "medium",
      summer: "low",
    });
  });
});

describe("summarize", () => {
  it("рахує загальне, вільний вибір і кредити по триместрах", () => {
    const items = [item(1, 1, 5), item(2, 1, 6), item(3, 2, 3, true)];
    expect(summarize(items)).toEqual({ total: 14, free: 3, byTrimester: { 1: 11, 2: 3, 3: 0 } });
  });
  it("порожній список дає нулі", () => {
    expect(summarize([])).toEqual({ total: 0, free: 0, byTrimester: { 1: 0, 2: 0, 3: 0 } });
  });
  it("ліміт вільного вибору 25", () => {
    expect(FREE_LIMIT).toBe(25);
  });
});

describe("dropVerdict", () => {
  const spring = disciplineFixture({ trimester: 2 });
  it("у свою колонку можна", () => {
    expect(dropVerdict(spring, 2)).toEqual({ ok: true });
  });
  it("у чужу колонку не можна й пояснюється, коли дисципліна викладається", () => {
    expect(dropVerdict(spring, 1)).toEqual({ ok: false, message: "Ця дисципліна викладається навесні" });
    expect(dropVerdict(disciplineFixture({ trimester: 1 }), 3)).toEqual({
      ok: false,
      message: "Ця дисципліна викладається восени",
    });
    expect(dropVerdict(disciplineFixture({ trimester: 3 }), 1)).toEqual({
      ok: false,
      message: "Ця дисципліна викладається влітку",
    });
  });
});
