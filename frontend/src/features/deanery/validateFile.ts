// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: validateFile.test.ts.
/** Швидка перевірка на клієнті; остаточно тип визначає сервер за вмістом файлу. */
export function validateDeaneryFile(file: { name: string; size: number }, maxBytes: number): string | null {
  if (file.size === 0) return "Файл порожній";
  if (file.size > maxBytes) return `Файл завеликий: максимум ${Math.round(maxBytes / 1_048_576)} МБ`;
  if (!/\.(pdf|docx)$/i.test(file.name)) return "Підтримуються лише PDF і DOCX";
  return null;
}
