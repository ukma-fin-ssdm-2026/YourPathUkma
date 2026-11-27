// Використання ШІ: Codex перевірив паузу САЗ після 429. Перевірка: Vitest.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { request, requestBlob } from "../../../api/client";
import { ApiError } from "../../../api/errors";
import { RemoteSazLogin } from "./RemoteSazLogin";

vi.mock("../../../api/client", () => ({ request: vi.fn(), requestBlob: vi.fn() }));

beforeEach(() => {
  vi.useFakeTimers();
  vi.mocked(request).mockReset().mockResolvedValue({ id: "login" });
  vi.mocked(requestBlob).mockReset();
  URL.createObjectURL = vi.fn(() => "blob:test");
  URL.revokeObjectURL = vi.fn();
});

afterEach(() => vi.useRealTimers());

async function start() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RemoteSazLogin connected={false} />
    </QueryClientProvider>,
  );
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "Підключити САЗ" })));
}

it("не опитує кадри до Retry-After і поновлює перевірку після паузи", async () => {
  vi.mocked(requestBlob)
    .mockRejectedValueOnce(new ApiError(429, "RATE_LIMITED", "limit", [], null, 2))
    .mockRejectedValue(new ApiError(409, "SAZ_LOGIN_PENDING", "pending"));
  await start();
  expect(screen.getByRole("alert")).toHaveTextContent("через 2 с");
  expect(screen.getByRole("button", { name: "Перевірити й зберегти сесію" })).toBeDisabled();
  await act(async () => vi.advanceTimersByTimeAsync(1999));
  expect(requestBlob).toHaveBeenCalledTimes(1);
  await act(async () => vi.advanceTimersByTimeAsync(1));
  expect(requestBlob).toHaveBeenCalledTimes(2);
  expect(screen.getByRole("button", { name: "Перевірити й зберегти сесію" })).toBeEnabled();
});

it("пауза після введення зупиняє також кадри і подальші натискання", async () => {
  vi.mocked(requestBlob).mockResolvedValue({
    blob: new Blob(["frame"]), filename: null,
    headers: new Headers({ "X-SAZ-Login-Host": "login.microsoftonline.com" }),
  });
  await start();
  vi.mocked(request).mockRejectedValue(new ApiError(429, "RATE_LIMITED", "limit", [], null, 2));
  const browser = screen.getByRole("button", { name: "Віддалений браузер САЗ" });
  await act(async () => fireEvent.keyDown(browser, { key: "a" }));
  expect(browser).toBeDisabled();
  await act(async () => fireEvent.keyDown(browser, { key: "b" }));
  await act(async () => vi.advanceTimersByTimeAsync(1999));
  expect(requestBlob).toHaveBeenCalledTimes(1);
  expect(request).toHaveBeenCalledTimes(2); // запуск входу й перше натискання
  await act(async () => vi.advanceTimersByTimeAsync(1));
  expect(requestBlob).toHaveBeenCalledTimes(2);
});
