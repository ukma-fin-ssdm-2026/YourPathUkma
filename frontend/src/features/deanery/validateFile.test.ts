// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { validateDeaneryFile } from "./validateFile";

const MAX = 10_485_760;

describe("validateDeaneryFile", () => {
  it("порожній файл", () => {
    expect(validateDeaneryFile({ name: "plan.pdf", size: 0 }, MAX)).toBe("Файл порожній");
  });
  it("завеликий файл", () => {
    expect(validateDeaneryFile({ name: "plan.pdf", size: MAX + 1 }, MAX)).toBe(
      "Файл завеликий: максимум 10 МБ",
    );
  });
  it("PDF і DOCX проходять незалежно від регістру", () => {
    expect(validateDeaneryFile({ name: "plan.PDF", size: 100 }, MAX)).toBeNull();
    expect(validateDeaneryFile({ name: "plan.docx", size: 100 }, MAX)).toBeNull();
  });
  it("інший тип відхиляється", () => {
    expect(validateDeaneryFile({ name: "plan.txt", size: 100 }, MAX)).toBe(
      "Підтримуються лише PDF і DOCX",
    );
  });
  it("порожній файл перевіряється раніше за тип", () => {
    expect(validateDeaneryFile({ name: "plan.txt", size: 0 }, MAX)).toBe("Файл порожній");
  });
});
