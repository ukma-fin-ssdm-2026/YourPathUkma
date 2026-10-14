// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { codeChallenge, randomUrlSafe } from "./pkce";

describe("pkce", () => {
  it("рахує code_challenge за вектором з RFC 7636", async () => {
    await expect(codeChallenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")).resolves.toBe(
      "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
    );
  });

  it("randomUrlSafe(32) дає 43 безпечні для URL символи", () => {
    const value = randomUrlSafe(32);
    expect(value).toHaveLength(43);
    expect(value).toMatch(/^[A-Za-z0-9_-]+$/);
  });

  it("два виклики дають різні значення", () => {
    expect(randomUrlSafe(16)).not.toBe(randomUrlSafe(16));
  });
});
