// Використання ШІ: файл створено за допомогою Claude (Anthropic) як результат Extract Method (Лаб 8). Перевірка: export.test.tsx, view.test.tsx.
// Спільна імітація завантаження файлу в jsdom: перехоплює клік по <a download> і збирає імена збережених файлів.
// Викликати на верхньому рівні тестового файлу: хуки beforeEach/afterEach реєструються тут.
export function mockDownloads(): string[] {
  const saved: string[] = [];
  let click: { mockRestore: () => void };

  beforeEach(() => {
    saved.length = 0;
    Object.assign(URL, { createObjectURL: vi.fn(() => "blob:test"), revokeObjectURL: vi.fn() });
    click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      saved.push(this.download);
    });
  });
  afterEach(() => click.mockRestore());

  return saved;
}
