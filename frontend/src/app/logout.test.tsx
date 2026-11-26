// Використання ШІ: Codex перевірив повідомлення та повтор logout для #220; Vitest.
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { toast } from "sonner";
import { setFetch } from "../api/client";
import { authResponse } from "../mocks/fixtures";
import { useSession } from "../auth/session";
import { ConnectedLayout } from "./ConnectedLayout";
vi.mock("sonner", () => ({ toast: { warning: vi.fn() } }));
it("warns after failed logout and retries server revocation", async () => {
  const fetchMock = vi
    .fn()
    .mockRejectedValueOnce(new TypeError("offline"))
    .mockResolvedValueOnce(new Response(null, { status: 204 }));
  setFetch(fetchMock);
  useSession.getState().setAuthenticated(authResponse());
  const router = createMemoryRouter([
    { path: "/", element: <ConnectedLayout /> },
    { path: "/login", element: <p>Вхід</p> },
  ]);
  render(<RouterProvider router={router} />);
  await userEvent.click(screen.getByRole("button", { name: "Вийти" }));
  expect(await screen.findByText("Вхід")).toBeInTheDocument();
  expect(toast.warning).toHaveBeenCalledWith(
    expect.stringContaining("Вихід не підтверджено"),
    expect.objectContaining({ duration: Infinity }),
  );
  const options = vi.mocked(toast.warning).mock.calls.at(-1)![1]!;
  await act(async () => {
    const action = options.action;
    if (typeof action !== "object" || action === null || !("onClick" in action)) {
      throw new Error("Expected a retry action");
    }
    action.onClick({} as never);
  });
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
});
