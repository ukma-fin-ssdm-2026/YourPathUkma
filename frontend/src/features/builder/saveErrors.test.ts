// Використання ШІ: тест створено Claude (Claude Code) у ЛР5 для знахідки security/detect-object-injection.
// Перевірка: npx vitest run src/features/builder/saveErrors.test.ts (падав до виправлення, проходить після).
import { describe, expect, it } from "vitest";
import { ApiError } from "../../api/errors";
import { describeSaveError } from "./saveErrors";

describe("describeSaveError: коди помилок від сервера не читають прототип Object", () => {
  it.each(["constructor", "toString", "__proto__", "hasOwnProperty"])(
    "код %s дає звичайне повідомлення",
    (code) => {
      const result = describeSaveError(new ApiError(409, code, "Сервер відхилив план"), []);
      expect(result.form).toEqual(["Сервер відхилив план"]);
    },
  );

  it("відомий код і далі перекладається", () => {
    const result = describeSaveError(new ApiError(409, "PLAN_NOT_EDITABLE", "x"), []);
    expect(result.form).toEqual(["Цей план уже подано, редагувати його не можна"]);
  });
});
