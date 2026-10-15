// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: download.test.ts.
/** Ім'я файлу з Content-Disposition: `filename*=UTF-8''…`, `filename="…"` або `filename=…`; інакше null. */
export function parseDispositionFilename(header: string | null): string | null {
  if (!header) return null;
  const encoded = /filename\*\s*=\s*[^']*''([^;]+)/i.exec(header)?.[1];
  if (encoded) {
    try {
      return decodeURIComponent(encoded.trim());
    } catch {
      // некоректне кодування: пробуємо звичайне filename нижче
    }
  }
  const plain = /filename\s*=\s*"([^"]+)"/i.exec(header)?.[1] ?? /filename\s*=\s*([^;\s]+)/i.exec(header)?.[1];
  return plain?.trim() || null;
}

export function filenameFromDisposition(header: string | null, fallback: string): string {
  return parseDispositionFilename(header) ?? fallback;
}

/** Зберігає Blob як файл через тимчасове посилання (звичайний <a href> не надішле Bearer-токен). */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
