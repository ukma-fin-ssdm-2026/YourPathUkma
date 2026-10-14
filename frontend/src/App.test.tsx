// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test.
import { render, screen } from "@testing-library/react";
import { App } from "./App";

describe("App", () => {
  it("поки сесія відновлюється, показує «Завантаження…»", () => {
    render(<App />);
    expect(screen.getByRole("status")).toHaveTextContent("Завантаження…");
  });
});
