// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { filenameFromDisposition, parseDispositionFilename, saveBlob } from "./download";

describe("parseDispositionFilename / filenameFromDisposition", () => {
  it("читає ім'я в лапках", () => {
    expect(parseDispositionFilename('attachment; filename="plan-2026.pdf"')).toBe("plan-2026.pdf");
  });
  it("читає ім'я без лапок", () => {
    expect(parseDispositionFilename("attachment; filename=plan-2026.pdf")).toBe("plan-2026.pdf");
  });
  it("читає закодоване filename*", () => {
    expect(
      parseDispositionFilename("attachment; filename*=UTF-8''%D0%BF%D0%BB%D0%B0%D0%BD.pdf"),
    ).toBe("план.pdf");
  });
  it("без заголовка або без імені дає null, а filenameFromDisposition запасне ім'я", () => {
    expect(parseDispositionFilename(null)).toBeNull();
    expect(parseDispositionFilename("attachment")).toBeNull();
    expect(filenameFromDisposition("", "x.pdf")).toBe("x.pdf");
    expect(filenameFromDisposition('attachment; filename="a.pdf"', "x.pdf")).toBe("a.pdf");
  });
});

describe("saveBlob", () => {
  it("клікає приховане посилання з потрібним ім'ям і звільняє URL", () => {
    const created = vi.fn(() => "blob:test");
    const revoked = vi.fn();
    Object.assign(URL, { createObjectURL: created, revokeObjectURL: revoked });
    const clicks: { download: string; href: string; inDom: boolean }[] = [];
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicks.push({
        download: this.download,
        href: this.href,
        inDom: document.body.contains(this),
      });
    });
    saveBlob(new Blob(["x"]), "plan-2026.pdf");
    expect(created).toHaveBeenCalledTimes(1);
    expect(clicks).toEqual([{ download: "plan-2026.pdf", href: "blob:test", inDom: true }]);
    expect(revoked).toHaveBeenCalledWith("blob:test");
    expect(document.querySelector("a[download]")).toBeNull();
    click.mockRestore();
  });
});
