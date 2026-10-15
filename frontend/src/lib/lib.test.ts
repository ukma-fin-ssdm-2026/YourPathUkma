// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { fieldErrors } from "../api/errors";
import { creditsPercent, formatCredits } from "./credits";
import { initials } from "./initials";
import { trimesterFromKey, trimesterKey, trimesterLabel } from "./trimester";

describe("formatCredits", () => {
  it("використовує кому для дробових", () => {
    expect(formatCredits(118.5)).toBe("118,5");
  });
  it("не додає зайвих знаків для цілих", () => {
    expect(formatCredits(60)).toBe("60");
  });
  it("показує нуль", () => {
    expect(formatCredits(0)).toBe("0");
  });
});

describe("creditsPercent", () => {
  it("рахує частку від ліміту", () => {
    expect(creditsPercent(118.5, 240)).toBeCloseTo(49.4, 1);
  });
  it("обмежує 100", () => {
    expect(creditsPercent(300, 240)).toBe(100);
  });
  it("дає 0 при нульовому ліміті, а не NaN", () => {
    expect(creditsPercent(10, 0)).toBe(0);
  });
});

describe("trimester", () => {
  it("мапить число в ключ і назад", () => {
    expect(trimesterKey(1)).toBe("autumn");
    expect(trimesterKey(2)).toBe("spring");
    expect(trimesterFromKey("summer")).toBe(3);
  });
  it("дає українську назву", () => {
    expect(trimesterLabel(1)).toBe("Осінь");
    expect(trimesterLabel(2)).toBe("Весна");
    expect(trimesterLabel(3)).toBe("Літо");
  });
});

describe("fieldErrors", () => {
  it("розкладає помилки по полях і по формі", () => {
    const result = fieldErrors([
      { field: "items.0.credits", message: "Input should be greater than 0" },
      { field: "body", message: "Value error, Перевищено ліміт вільного вибору" },
    ]);
    expect(result.fields["items.0.credits"]).toBe("Input should be greater than 0");
    expect(result.form).toEqual(["Перевищено ліміт вільного вибору"]);
  });

  it("порожнє поле теж іде у форму", () => {
    expect(fieldErrors([{ field: "", message: "Щось не так" }]).form).toEqual(["Щось не так"]);
  });
});

describe("initials", () => {
  it("бере першу й останню літеру слів", () => {
    expect(initials("Владислав Смирнов")).toBe("ВС");
    expect(initials("Олександра Вишневська-Коваленко")).toBe("ОВ");
    expect(initials("Іван Петрович Коваль")).toBe("ІК");
  });

  it("з одного слова дає одну літеру", () => {
    expect(initials("Йо")).toBe("Й");
  });

  it("порожнє ім'я дає «?»", () => {
    expect(initials("   ")).toBe("?");
  });

  it("не ламає емодзі на початку імені", () => {
    expect(initials("👩‍💻 Марія")).toBe("👩‍💻М");
  });
});
