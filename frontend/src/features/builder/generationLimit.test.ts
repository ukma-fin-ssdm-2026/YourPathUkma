// Використання ШІ: Codex перевірив причини 429. Перевірка: Vitest.
import { ApiError } from "../../api/errors";
import { generationStartError } from "./usePlanGeneration";

it("розрізняє загальний і добовий ліміти генерації", () => {
  expect(generationStartError(new ApiError(429, "RATE_LIMITED", "limit", [], null, 30)))
    .toBe("Забагато запитів. Спробуйте через 30 с.");
  expect(generationStartError(new ApiError(
    429, "RATE_LIMITED", "limit", [{ field: "rate_limit", message: "ai_daily" }], null, 3600,
  ))).toBe("Вичерпано добовий ліміт генерацій. Спробуйте через 1 год.");
});
