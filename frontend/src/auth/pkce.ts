// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: pkce.test.ts (вектор RFC 7636).
function toBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Випадковий рядок, безпечний для URL: 32 байти дають 43 символи. */
export function randomUrlSafe(byteLength: number): string {
  return toBase64Url(crypto.getRandomValues(new Uint8Array(byteLength)));
}

/** PKCE S256: base64url(SHA-256(verifier)). */
export async function codeChallenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return toBase64Url(new Uint8Array(digest));
}
