// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { render, screen } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router";
import { AppLayout } from "./AppLayout";
import type { Role } from "./nav";

function renderLayout(role: Role, initialPath = "/") {
  const router = createMemoryRouter(
    [
      {
        element: <AppLayout role={role} userName="Владислав" />,
        children: [
          { path: "/", element: <p>головна</p> },
          { path: "/catalog", element: <p>каталог</p> },
        ],
      },
    ],
    { initialEntries: [initialPath] },
  );
  render(<RouterProvider router={router} />);
}

describe("AppLayout", () => {
  it("не показує «Адмінка» студенту", () => {
    renderLayout("student");
    expect(screen.getByRole("link", { name: "Профіль" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Адмінка" })).not.toBeInTheDocument();
  });

  it("показує «Адмінка» адміністратору", () => {
    renderLayout("admin");
    expect(screen.getByRole("link", { name: "Адмінка" })).toBeInTheDocument();
  });

  it("позначає лише поточний маршрут як aria-current", () => {
    renderLayout("student", "/catalog");
    expect(screen.getByRole("link", { name: "Каталог" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Профіль" })).not.toHaveAttribute("aria-current");
  });

  it("показує ім'я користувача й вміст маршруту", () => {
    renderLayout("student");
    expect(screen.getByText("Владислав")).toBeInTheDocument();
    expect(screen.getByText("головна")).toBeInTheDocument();
  });
});
