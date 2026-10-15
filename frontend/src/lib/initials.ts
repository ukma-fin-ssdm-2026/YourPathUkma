// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: lib.test.ts.
const segmenter = new Intl.Segmenter("uk", { granularity: "grapheme" });

const firstGrapheme = (word: string): string => {
  const first = segmenter.segment(word)[Symbol.iterator]().next().value;
  return first ? first.segment.toLocaleUpperCase("uk") : "";
};

/** «Владислав Смирнов» → «ВС»; одне слово дає одну літеру; порожнє ім'я дає «?». Емодзі лишається цілою графемою. */
export function initials(name: string): string {
  const words = name.split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  const picked = words.length === 1 ? [words[0]!] : [words[0]!, words[words.length - 1]!];
  return picked.map(firstGrapheme).join("");
}
