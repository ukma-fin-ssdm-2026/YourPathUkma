// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тест спершу впав).
import { encodeMultipart } from "./multipart";

describe("encodeMultipart", () => {
  it("кодує поля й файл у multipart/form-data", async () => {
    const form = new FormData();
    form.append("academic_year", "2026");
    form.append("file", new File(["вміст файлу"], "plan_2026.pdf", { type: "application/pdf" }));
    const { contentType, body } = await encodeMultipart(form);
    expect(contentType.startsWith("multipart/form-data; boundary=")).toBe(true);
    const text = new TextDecoder().decode(body);
    expect(text).toContain('name="academic_year"');
    expect(text).toContain("2026");
    expect(text).toContain('filename="plan_2026.pdf"');
    expect(text).toContain("Content-Type: application/pdf");
    expect(text).toContain("вміст файлу");
    expect(text.trimEnd().endsWith("--")).toBe(true);
  });
});
