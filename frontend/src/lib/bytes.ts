// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: documents.test.tsx.
const oneDecimal = new Intl.NumberFormat("uk-UA", { maximumFractionDigits: 1 });

/** 184233 → «180 КБ», 2516582 → «2,4 МБ». */
export function formatBytes(bytes: number): string {
  if (bytes < 1_048_576) return `${Math.round(bytes / 1024)} КБ`;
  return `${oneDecimal.format(bytes / 1_048_576)} МБ`;
}
