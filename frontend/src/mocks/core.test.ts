// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test.
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "./server";
import { coreHandlers, resetCoreMocks } from "./core";

const items = [
  { course_id: 101, title: "Курс", trimester: 1, credits: 5, is_free_elective: false },
];
const plan = {
  academic_year: 2026,
  course: 3,
  load_levels: { autumn: "medium", spring: "medium", summer: "medium" },
  items,
};

async function call(path: string, method = "GET", body?: unknown, token = true) {
  const response = await fetch(`http://localhost/api/v1${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: "Bearer t" } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  return { status: response.status, json: text ? JSON.parse(text) : null };
}

describe("режим full: обробники ✅-ендпоінтів", () => {
  beforeEach(() => {
    server.use(...coreHandlers);
    resetCoreMocks();
  });

  it("фільтрує каталог за напрямком і семестром", async () => {
    const { json } = await call("/disciplines?direction=Кібербезпека&trimester=3");
    expect(json.disciplines.map((d: { id: number }) => d.id)).toEqual([103]);
  });

  it("відмовляє в каталозі й планах без токена", async () => {
    expect((await call("/disciplines", "GET", undefined, false)).status).toBe(401);
    expect((await call("/plans", "GET", undefined, false)).status).toBe(401);
  });

  it("створює, оновлює, подає й після подання не дає редагувати план", async () => {
    const created = await call("/plans", "POST", plan);
    expect(created.json).toMatchObject({ status: "draft", total_credits: 5 });
    const id = created.json.id;
    expect((await call(`/plans/${id}`, "PUT", { ...plan, items: [] })).json.total_credits).toBe(0);
    expect((await call(`/plans/${id}/submit`, "POST")).json.status).toBe("submitted");
    expect((await call(`/plans/${id}`, "PUT", plan)).status).toBe(409);
  });

  it("новий напрям із адмінки одразу видно в загальному довіднику", async () => {
    const created = await call("/admin/directions", "POST", { name: "Квантові обчислення" });
    expect(created.status).toBe(201);
    const { json } = await call("/directions");
    expect(json.directions.map((d: { name: string }) => d.name)).toContain("Квантові обчислення");
  });

  it("validate відхиляє дублікати дисциплін", async () => {
    const { json } = await call("/plans/validate", "POST", {
      ...plan,
      items: [...items, ...items],
    });
    expect(json.errors.map((e: { code: string }) => e.code)).toContain("DUPLICATE_COURSE");
  });
});
