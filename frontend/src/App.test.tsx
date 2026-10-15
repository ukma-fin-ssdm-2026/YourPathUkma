// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test.
import { render, screen } from "@testing-library/react";
import { App } from "./App";

describe("App", () => {
  it("показує назву застосунку й навігацію", () => {
    render(<App />);
    expect(screen.getByRole("link", { name: "YourPath" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Основна навігація" })).toBeInTheDocument();
  });
});
