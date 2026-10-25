// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: npm test (тести спершу впали).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { request } from "../../api/client";
import type { DeaneryDocument } from "../../api/types";
import { setAccessToken } from "../../api/token";
import { db } from "../../mocks/db";
import {
  useDeaneryDocument,
  useDeaneryDocuments,
  useDeleteDocument,
  useUploadDocument,
} from "./useDeanery";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const pdf = (name: string) => new File(["вміст"], name, { type: "application/pdf" });

async function uploadViaApi(name: string, year = 2026): Promise<DeaneryDocument> {
  const form = new FormData();
  form.append("file", pdf(name));
  form.append("academic_year", String(year));
  return request<DeaneryDocument>("/deanery-documents", { method: "POST", body: form });
}

beforeEach(() => setAccessToken("t"));

describe("завантаження й список", () => {
  it("завантажений файл стає pending-документом у списку", async () => {
    const { result } = renderHook(
      () => ({ upload: useUploadDocument(), list: useDeaneryDocuments(2026) }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.list.isSuccess).toBe(true));
    expect(result.current.list.data?.deanery_documents).toEqual([]);

    let created: DeaneryDocument | undefined;
    await act(async () => {
      created = await result.current.upload.mutateAsync({
        file: pdf("plan_2026.pdf"),
        academicYear: 2026,
      });
    });
    expect(created).toMatchObject({
      original_filename: "plan_2026.pdf",
      academic_year: 2026,
      parse_status: "pending",
    });
    await waitFor(() => expect(result.current.list.data?.deanery_documents).toHaveLength(1));
  });

  it("сервер відхиляє завеликий файл кодом 413", async () => {
    const { result } = renderHook(() => useUploadDocument(), { wrapper });
    await act(async () => {
      await expect(
        result.current.mutateAsync({ file: pdf("huge.pdf"), academicYear: 2026 }),
      ).rejects.toMatchObject({ status: 413, code: "FILE_TOO_LARGE" });
    });
  });

  it("сервер відхиляє невідомий тип кодом 415", async () => {
    const { result } = renderHook(() => useUploadDocument(), { wrapper });
    await act(async () => {
      await expect(
        result.current.mutateAsync({ file: new File(["x"], "notes.txt"), academicYear: 2026 }),
      ).rejects.toMatchObject({ status: 415, code: "UNSUPPORTED_FILE_TYPE" });
    });
  });
});

describe("розпізнавання", () => {
  it("опитування доводить документ від pending до parsed з нормативними", async () => {
    const doc = await uploadViaApi("plan_2026.pdf");
    const { result } = renderHook(() => useDeaneryDocument(doc.id, { pollMs: 20 }), { wrapper });
    await waitFor(() => expect(result.current.data?.parse_status).toBe("parsed"), {
      timeout: 3000,
    });
    const courses = result.current.data!.normative_courses;
    expect(courses).toHaveLength(4);
    expect(courses.filter((c) => c.course_id === null)).toHaveLength(1);
  });

  it("scan.pdf завершується failed із причиною, і опитування зупиняється", async () => {
    const doc = await uploadViaApi("scan.pdf");
    const { result } = renderHook(() => useDeaneryDocument(doc.id, { pollMs: 20 }), { wrapper });
    await waitFor(() => expect(result.current.data?.parse_status).toBe("failed"), {
      timeout: 3000,
    });
    expect(result.current.data?.parse_error).toBe("Не вдалося прочитати таблицю дисциплін");
    const pollsAfterFailure = db.docPolls[doc.id];
    await new Promise((resolve) => setTimeout(resolve, 150));
    expect(db.docPolls[doc.id]).toBe(pollsAfterFailure);
  });

  it("неіснуючий документ дає 404 DOCUMENT_NOT_FOUND", async () => {
    const { result } = renderHook(() => useDeaneryDocument(999), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toMatchObject({ status: 404, code: "DOCUMENT_NOT_FOUND" });
  });

  it("без id запит не виконується", () => {
    const { result } = renderHook(() => useDeaneryDocument(null), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
  });
});

describe("видалення", () => {
  it("прибирає документ зі списку", async () => {
    const doc = await uploadViaApi("plan_2026.pdf");
    const { result } = renderHook(
      () => ({ list: useDeaneryDocuments(2026), remove: useDeleteDocument() }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.list.data?.deanery_documents).toHaveLength(1));
    await act(async () => {
      await result.current.remove.mutateAsync(doc.id);
    });
    await waitFor(() => expect(result.current.list.data?.deanery_documents).toEqual([]));
  });

  it("документ, що використовується в плані, дає 409 DOCUMENT_IN_USE", async () => {
    const doc = await uploadViaApi("inuse.pdf");
    const { result } = renderHook(() => useDeleteDocument(), { wrapper });
    await act(async () => {
      await expect(result.current.mutateAsync(doc.id)).rejects.toMatchObject({
        status: 409,
        code: "DOCUMENT_IN_USE",
      });
    });
  });
});
