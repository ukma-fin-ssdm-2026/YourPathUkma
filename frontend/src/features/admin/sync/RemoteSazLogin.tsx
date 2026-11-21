// Використання ШІ: екран віддаленого входу до САЗ додано Codex. Перевірка: Vitest і typecheck.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { request, requestBlob } from "../../../api/client";
import { ApiError } from "../../../api/errors";
import { Button } from "../../../ui/Button";
import { Card } from "../../../ui/Card";

const SESSION = "/admin/saz-session";
const SESSION_QUERY = ["admin", "saz-session"];
const BROWSER_KEYS = new Set([
  "Enter", "Tab", "Backspace", "Delete", "Escape", "ArrowUp", "ArrowDown", "ArrowLeft",
  "ArrowRight", "Home", "End", "PageUp", "PageDown",
]);

type BrowserInput =
  | { kind: "click"; x: number; y: number }
  | { kind: "key"; key: string }
  | { kind: "text"; text: string };

export function useSazSession(enabled: boolean) {
  return useQuery({
    queryKey: SESSION_QUERY,
    queryFn: () => request<{ connected: boolean }>(SESSION),
    enabled,
    retry: false,
  });
}

export function RemoteSazLogin({ connected }: { connected: boolean }) {
  const queryClient = useQueryClient();
  const [loginId, setLoginId] = useState<string | null>(null);
  const [frame, setFrame] = useState<{ url: string; host: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const inputQueue = useRef(Promise.resolve());
  const activeLogin = useRef<string | null>(null);

  useEffect(() => {
    if (!loginId) return;
    let stopped = false;
    let url: string | undefined;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();

    async function refreshFrame() {
      try {
        const result = await requestBlob(`${SESSION}/login/${loginId}/frame`, {
          accept: "image/jpeg",
          signal: controller.signal,
        });
        if (stopped) return;
        const host = result.headers.get("X-SAZ-Login-Host");
        if (!host) throw new Error("Missing browser origin");
        if (url) URL.revokeObjectURL(url);
        url = URL.createObjectURL(result.blob);
        setFrame({ url, host });
      } catch (failure) {
        if (stopped) return;
        if (failure instanceof ApiError && failure.code === "SAZ_LOGIN_NOT_FOUND") {
          setError(failure.message);
          activeLogin.current = null;
          setLoginId(null);
          return;
        }
        if (failure instanceof ApiError && failure.code === "SAZ_LOGIN_PENDING") {
          setFrame(null);
        } else {
          setError(failure instanceof ApiError ? failure.message : "Не вдалося отримати кадр браузера");
        }
      }
      if (!stopped) timer = setTimeout(refreshFrame, 700);
    }

    void refreshFrame();
    return () => {
      stopped = true;
      controller.abort();
      clearTimeout(timer);
      if (url) URL.revokeObjectURL(url);
      if (activeLogin.current !== loginId) return;
      activeLogin.current = null;
      void request(`${SESSION}/login/${loginId}`, { method: "DELETE" }).catch(() => undefined);
    };
  }, [loginId]);

  async function perform(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : "Не вдалося виконати дію");
    } finally {
      setBusy(false);
    }
  }

  function send(input: BrowserInput) {
    if (!loginId || !frame || busy) return;
    inputQueue.current = inputQueue.current
      .then(async () => {
        if (activeLogin.current === loginId) {
          await request(`${SESSION}/login/${loginId}/input`, { method: "POST", body: { host: frame.host, action: input } });
        }
      })
      .catch((failure: unknown) => {
        if (activeLogin.current === loginId) {
          setError(failure instanceof ApiError ? failure.message : "Не вдалося передати дію до браузера");
        }
      });
  }

  function handleKey(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.altKey || event.metaKey || event.nativeEvent.isComposing) return;
    if (event.key === "Escape") {
      event.currentTarget.blur();
      return;
    }
    let input: BrowserInput | undefined;
    if (event.ctrlKey) {
      if (event.key.toLowerCase() === "a") input = { kind: "key", key: "Control+A" };
    } else if (BROWSER_KEYS.has(event.key)) {
      input = { kind: "key", key: event.shiftKey && event.key === "Tab" ? "Shift+Tab" : event.key };
    } else if (Array.from(event.key).length === 1) {
      input = { kind: "text", text: event.key };
    }
    if (input) {
      event.preventDefault();
      send(input);
    }
  }

  return (
    <Card className="mt-4 space-y-3">
      {loginId ? (
        <>
          <p>Увійдіть у САЗ через Microsoft. Натисніть на кадр браузера, щоб вводити з клавіатури. Esc повертає керування сторінці.</p>
          {frame && <p className="text-sm text-ink-2">{frame.host}</p>}
          {frame ? (
            <button
              type="button"
              className="block w-full cursor-crosshair overflow-hidden rounded border border-rule"
              aria-label="Віддалений браузер САЗ"
              disabled={busy}
              onKeyDown={handleKey}
              onClick={(event) => {
                if (!event.detail) return;
                const bounds = event.currentTarget.getBoundingClientRect();
                send({
                  kind: "click",
                  x: (event.clientX - bounds.left) / bounds.width,
                  y: (event.clientY - bounds.top) / bounds.height,
                });
              }}
            >
              <img src={frame.url} alt={`Вікно входу на ${frame.host}`} className="block w-full" />
            </button>
          ) : (
            <p>Завантаження вікна входу…</p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={busy}
              onClick={() => void perform(async () => {
                await inputQueue.current;
                await request(`${SESSION}/login/${loginId}/complete`, { method: "POST" });
                activeLogin.current = null;
                setLoginId(null);
                await queryClient.invalidateQueries({ queryKey: SESSION_QUERY });
              })}
            >
              Перевірити й зберегти сесію
            </Button>
            <Button disabled={busy} onClick={() => setLoginId(null)}>Скасувати</Button>
          </div>
        </>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <p>{connected ? "Сесію САЗ збережено" : "Підключіть САЗ, щоб запустити парсинг"}</p>
          <Button
            disabled={busy}
            onClick={() => void perform(async () => {
              const result = await request<{ id: string }>(`${SESSION}/login`, { method: "POST" });
              setFrame(null);
              activeLogin.current = result.id;
              setLoginId(result.id);
            })}
          >
            {connected ? "Підключити САЗ повторно" : "Підключити САЗ"}
          </Button>
          {connected && (
            <Button disabled={busy} onClick={() => void perform(async () => {
              await request(SESSION, { method: "DELETE" });
              await queryClient.invalidateQueries({ queryKey: SESSION_QUERY });
            })}>
              Відключити САЗ
            </Button>
          )}
        </div>
      )}
      {error && <p role="alert" className="text-bad">{error}</p>}
    </Card>
  );
}
