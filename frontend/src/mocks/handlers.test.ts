// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { request } from "../api/client";
import { setAccessToken } from "../api/token";
import type { AuthResponse, Me } from "../api/types";

const validBody = { course_year: 3, specialty: "Інженерія програмного забезпечення" };

describe("моки автентифікації", () => {
  it("refresh без входу дає 401, після входу через Microsoft дає 200", async () => {
    await expect(request("/auth/refresh", { method: "POST", auth: false })).rejects.toMatchObject({
      status: 401,
      code: "UNAUTHORIZED",
    });
    const login = await request<AuthResponse>("/auth/microsoft", {
      method: "POST",
      auth: false,
      body: {
        code: "c",
        code_verifier: "v".repeat(43),
        redirect_uri: "http://localhost:5173/auth/callback",
      },
    });
    expect(login.user).toMatchObject({ id: 42, role: "student" });
    await expect(
      request<AuthResponse>("/auth/refresh", { method: "POST", auth: false }),
    ).resolves.toMatchObject({ token_type: "Bearer", expires_in: 900 });
  });

  it("logout повертає undefined і скидає сесію", async () => {
    await request("/auth/microsoft", { method: "POST", auth: false, body: {} });
    await expect(request("/auth/logout", { method: "POST", auth: false })).resolves.toBeUndefined();
    await expect(request("/auth/refresh", { method: "POST", auth: false })).rejects.toMatchObject({
      status: 401,
    });
  });
});

describe("моки /me", () => {
  it("без токена дає UNAUTHORIZED", async () => {
    await expect(request("/me")).rejects.toMatchObject({ code: "UNAUTHORIZED" });
  });

  it("з токеном повертає студента без онбордингу", async () => {
    setAccessToken("t");
    const me = await request<Me>("/me");
    expect(me.student).toMatchObject({
      course_year: null,
      onboarding_required: true,
      can_create_plan: false,
    });
    expect(me.student?.credits).toMatchObject({ total_used: 0, total_limit: 240 });
  });
});

describe("моки онбордингу", () => {
  beforeEach(() => setAccessToken("t"));

  it("курс 5 дає 422 з полем course_year", async () => {
    const error = await request("/me/onboarding", {
      method: "POST",
      body: { ...validBody, course_year: 5 },
    }).catch((e: unknown) => e);
    expect(error).toMatchObject({ status: 422, code: "VALIDATION_ERROR" });
    expect((error as { details: { field: string }[] }).details.map((d) => d.field)).toContain(
      "course_year",
    );
  });

  it("надто коротка спеціальність дає 422 з полем specialty", async () => {
    const error = await request("/me/onboarding", {
      method: "POST",
      body: { course_year: 3, specialty: "І" },
    }).catch((e: unknown) => e);
    expect((error as { details: { field: string }[] }).details.map((d) => d.field)).toContain(
      "specialty",
    );
  });

  it("4 курс: навантаження auto, план створювати можна", async () => {
    const me = await request<Me>("/me/onboarding", {
      method: "POST",
      body: { ...validBody, course_year: 4 },
    });
    expect(me.student).toMatchObject({
      course_year: 4,
      course_year_source: "self_declared",
      onboarding_required: false,
      can_create_plan: true,
      load_levels_mode: "auto",
    });
  });

  it("1 курс: плани створювати не можна, навантаження manual", async () => {
    const me = await request<Me>("/me/onboarding", {
      method: "POST",
      body: { ...validBody, course_year: 1 },
    });
    expect(me.student).toMatchObject({ can_create_plan: false, load_levels_mode: "manual" });
  });

  it("повторний онбординг дає 409 ALREADY_ONBOARDED", async () => {
    await request("/me/onboarding", { method: "POST", body: validBody });
    await expect(
      request("/me/onboarding", { method: "POST", body: validBody }),
    ).rejects.toMatchObject({
      status: 409,
      code: "ALREADY_ONBOARDED",
    });
  });
});
