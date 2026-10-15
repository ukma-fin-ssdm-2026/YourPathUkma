// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider, createMemoryRouter } from "react-router";
import { AdminLayout } from "./AdminLayout";
import { OverviewPage } from "./OverviewPage";

function renderAdmin(entry = "/admin") {
  const router = createMemoryRouter(
    [
      {
        path: "/admin",
        element: <AdminLayout />,
        children: [
          { index: true, element: <OverviewPage /> },
          { path: "moderation", element: <p>екран модерації</p> },
          { path: "sync", element: <p>екран синхронізації</p> },
          { path: "users", element: <p>екран користувачів</p> },
          { path: "directions", element: <p>екран напрямків</p> },
          { path: "audit", element: <p>екран журналу</p> },
        ],
      },
    ],
    { initialEntries: [entry] },
  );
  render(<RouterProvider router={router} />);
  return router;
}

describe("AdminLayout", () => {
  it("рендерить бічне меню з шістьма пунктами та позначає поточний", () => {
    renderAdmin("/admin/sync");
    const menu = screen.getByRole("navigation", { name: "Розділи адмінки" });
    const labels = within(menu)
      .getAllByRole("link")
      .map((link) => link.textContent);
    expect(labels).toEqual([
      "Огляд",
      "Модерація",
      "Синхронізація",
      "Користувачі",
      "Напрямки",
      "Журнал дій",
    ]);
    expect(within(menu).getByRole("link", { name: "Синхронізація" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(menu).getByRole("link", { name: "Огляд" })).not.toHaveAttribute("aria-current");
  });

  it("пункт «Огляд» активний лише на /admin, а не на вкладених маршрутах", () => {
    renderAdmin("/admin");
    const menu = screen.getByRole("navigation", { name: "Розділи адмінки" });
    expect(within(menu).getByRole("link", { name: "Огляд" })).toHaveAttribute("aria-current", "page");
  });

  it("перехід по пункту меню показує відповідний екран", async () => {
    renderAdmin("/admin");
    await userEvent.click(screen.getByRole("link", { name: "Користувачі" }));
    expect(screen.getByText("екран користувачів")).toBeInTheDocument();
  });
});

describe("OverviewPage", () => {
  it("картки огляду ведуть у розділи", () => {
    renderAdmin("/admin");
    const overview = screen.getByRole("region", { name: "Огляд адмінки" });
    const href = (name: RegExp) => within(overview).getByRole("link", { name }).getAttribute("href");
    expect(href(/^Модерація/)).toBe("/admin/moderation");
    expect(href(/^Синхронізація/)).toBe("/admin/sync");
    expect(href(/^Користувачі/)).toBe("/admin/users");
    expect(href(/^Напрямки/)).toBe("/admin/directions");
    expect(href(/^Журнал дій/)).toBe("/admin/audit");
  });
});
