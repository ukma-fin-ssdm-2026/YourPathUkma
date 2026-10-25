// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setAccessToken } from "../../../api/token";
import { server } from "../../../mocks/server";
import { adminUserFixture } from "../../../test/handlers";
import { UsersPage } from "./UsersPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <UsersPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => setAccessToken("t"));

async function openEditor(name: RegExp) {
  const row = await screen.findByRole("row", { name });
  await userEvent.click(within(row).getByRole("button", { name: "Змінити" }));
  return screen.getByRole("dialog", { name: "Змінити користувача" });
}

describe("UserEditor", () => {
  it("«Змінити» відкриває форму з поточними значеннями; «Зберегти» неактивна без змін", async () => {
    renderPage();
    const dialog = await openEditor(/Владислав/);
    expect(within(dialog).getByLabelText("Курс")).toHaveValue("3");
    expect(within(dialog).getByLabelText("Спеціальність")).toHaveValue(
      "Інженерія програмного забезпечення",
    );
    expect(within(dialog).getByRole("button", { name: "Студент" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(dialog).getByRole("button", { name: "Зберегти" })).toBeDisabled();
  });

  it("збереження надсилає лише змінені поля й закриває форму", async () => {
    const bodies: string[] = [];
    server.use(
      http.patch("*/api/v1/admin/users/:id", async ({ request }) => {
        bodies.push(await request.text());
        return HttpResponse.json(adminUserFixture());
      }),
    );
    renderPage();
    await openEditor(/Владислав/);
    await userEvent.selectOptions(screen.getByLabelText("Курс"), "4");
    await userEvent.click(screen.getByRole("button", { name: "Зберегти" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(bodies).toEqual(['{"student":{"course_year":4}}']);
  });

  it("зміна курсу оновлює рядок і ставить джерело «Адмін»", async () => {
    renderPage();
    await openEditor(/Владислав/);
    await userEvent.selectOptions(screen.getByLabelText("Курс"), "4");
    await userEvent.click(screen.getByRole("button", { name: "Зберегти" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await waitFor(() => {
      const student = screen.getByRole("row", { name: /Владислав/ });
      expect(within(student).getByText("4")).toBeInTheDocument();
      expect(within(student).getByText("Адмін")).toBeInTheDocument();
    });
  });

  it("409 CANNOT_CHANGE_OWN_ROLE: повідомлення, форма лишається відкритою зі значеннями", async () => {
    renderPage();
    const dialog = await openEditor(/Адміністратор/);
    await userEvent.click(within(dialog).getByRole("button", { name: "Студент" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Зберегти" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "Не можна змінити власну роль",
    );
    expect(within(dialog).getByRole("button", { name: "Студент" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("422 показує помилку біля поля спеціальності", async () => {
    server.use(
      http.patch("*/api/v1/admin/users/:id", () =>
        HttpResponse.json(
          {
            code: "VALIDATION_ERROR",
            message: "x",
            details: [{ field: "student.specialty", message: "Спеціальність занадто довга" }],
          },
          { status: 422 },
        ),
      ),
    );
    renderPage();
    await openEditor(/Владислав/);
    await userEvent.type(screen.getByLabelText("Спеціальність"), "!");
    await userEvent.click(screen.getByRole("button", { name: "Зберегти" }));
    expect(await screen.findByText("Спеціальність занадто довга")).toBeInTheDocument();
  });

  it("клієнтська перевірка не пропускає надто коротку спеціальність", async () => {
    renderPage();
    await openEditor(/Владислав/);
    const field = screen.getByLabelText("Спеціальність");
    await userEvent.clear(field);
    await userEvent.type(field, "А");
    await userEvent.click(screen.getByRole("button", { name: "Зберегти" }));
    expect(screen.getByText("Від 2 до 150 символів")).toBeInTheDocument();
  });

  it("для адміна без профілю студента курс і спеціальність приховані", async () => {
    renderPage();
    const dialog = await openEditor(/Адміністратор/);
    expect(within(dialog).queryByLabelText("Курс")).not.toBeInTheDocument();
    expect(within(dialog).queryByLabelText("Спеціальність")).not.toBeInTheDocument();
  });

  it("Escape закриває форму", async () => {
    renderPage();
    await openEditor(/Владислав/);
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
