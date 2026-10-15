// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тест спершу впав).
import { render, screen } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router";
import { appRoutes } from "./routes";

function renderAt(path: string, routes = appRoutes) {
  render(<RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />);
}

describe("сторінки помилок", () => {
  it("невідома адреса показує сторінку 404 українською з посиланням на головну", async () => {
    renderAt("/nope");
    expect(
      await screen.findByRole("heading", { name: "Сторінку не знайдено" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "На головну" })).toHaveAttribute("href", "/");
  });

  it("помилка екрана показує зрозуміле повідомлення замість англомовного екрана React Router", async () => {
    const Broken = () => {
      throw new Error("boom");
    };
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    renderAt("/broken", [
      {
        errorElement: appRoutes[0]!.errorElement,
        children: [{ path: "/broken", element: <Broken /> }],
      },
    ]);
    expect(await screen.findByRole("heading", { name: "Щось пішло не так" })).toBeInTheDocument();
    expect(screen.queryByText(/Hey developer/)).not.toBeInTheDocument();
    consoleError.mockRestore();
  });
});
