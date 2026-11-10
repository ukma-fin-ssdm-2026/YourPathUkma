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

  it.each([1, 2, 3, 16, 31, 32])("randomUrlSafe(%i) не містить base64-доповнення '='", (bytes) => {
    const value = randomUrlSafe(bytes);
    expect(value).not.toContain("=");
    expect(value).toMatch(/^[A-Za-z0-9_-]+$/);
    // base64 без доповнення: ceil(bytes * 4 / 3) символів
    expect(value).toHaveLength(Math.ceil((bytes * 4) / 3));
  });

  it("два виклики дають різні значення", () => {
    expect(randomUrlSafe(16)).not.toBe(randomUrlSafe(16));
  });
});
