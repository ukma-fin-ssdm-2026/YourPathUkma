// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: multipart.test.ts.
// Тестовий допоміжний код: у jsdom FormData і Blob не сумісні з undici (Node fetch), тому будуємо тіло вручну.
function readBytes(blob: Blob): Promise<Uint8Array> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(new Uint8Array(reader.result as ArrayBuffer));
    reader.onerror = () => reject(reader.error);
    reader.readAsArrayBuffer(blob);
  });
}

function concat(parts: Uint8Array[]): Uint8Array {
  const out = new Uint8Array(parts.reduce((total, part) => total + part.length, 0));
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

export async function encodeMultipart(
  form: FormData,
): Promise<{ contentType: string; body: Uint8Array }> {
  const boundary = `----vitest${Math.random().toString(16).slice(2)}`;
  const encoder = new TextEncoder();
  const parts: Uint8Array[] = [];
  for (const [name, value] of form.entries()) {
    if (typeof value === "string") {
      parts.push(
        encoder.encode(`--${boundary}\r\nContent-Disposition: form-data; name="${name}"\r\n\r\n${value}\r\n`),
      );
    } else {
      parts.push(
        encoder.encode(
          `--${boundary}\r\nContent-Disposition: form-data; name="${name}"; filename="${value.name}"\r\n` +
            `Content-Type: ${value.type || "application/octet-stream"}\r\n\r\n`,
        ),
        await readBytes(value),
        encoder.encode("\r\n"),
      );
    }
  }
  parts.push(encoder.encode(`--${boundary}--\r\n`));
  return { contentType: `multipart/form-data; boundary=${boundary}`, body: concat(parts) };
}
