// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тест спершу впав).
import { render, screen } from "@testing-library/react";
import { App } from "./App";

describe("App", () => {
  it("показує назву застосунку", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "YourPath" })).toBeInTheDocument();
  });
});
