// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: deanery-data.test.tsx.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { request } from "../../api/client";
import type { ApiError } from "../../api/errors";
import type { DeaneryDocument } from "../../api/types";

const LIST_KEY = ["deanery-documents"] as const;

export function useDeaneryDocuments(academicYear: number) {
  return useQuery({
    queryKey: [...LIST_KEY, academicYear],
    queryFn: () =>
      request<{ deanery_documents: DeaneryDocument[] }>("/deanery-documents", {
        query: { academic_year: academicYear },
      }),
  });
}

/** Один документ; поки він розпізнається, опитується кожні `pollMs` (2 с за контрактом). */
export function useDeaneryDocument(id: number | null, options: { pollMs?: number } = {}) {
  const queryClient = useQueryClient();
  const pollMs = options.pollMs ?? 2000;
  const query = useQuery({
    queryKey: ["deanery-document", id],
    queryFn: () => request<DeaneryDocument>(`/deanery-documents/${id}`),
    enabled: id !== null,
    refetchInterval: (q) => (q.state.data?.parse_status === "pending" ? pollMs : false),
  });

  // Коли розпізнавання завершилось, список теж має оновити статус.
  const status = query.data?.parse_status;
  const previous = useRef(status);
  useEffect(() => {
    if (previous.current === "pending" && status && status !== "pending") {
      void queryClient.invalidateQueries({ queryKey: LIST_KEY });
    }
    previous.current = status;
  }, [status, queryClient]);

  return query;
}

export function useUploadDocument() {
  const queryClient = useQueryClient();
  return useMutation<DeaneryDocument, ApiError, { file: File; academicYear: number }>({
    mutationFn: ({ file, academicYear }) => {
      const form = new FormData();
      form.append("file", file);
      form.append("academic_year", String(academicYear));
      return request<DeaneryDocument>("/deanery-documents", { method: "POST", body: form });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: LIST_KEY }),
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation<void, ApiError, number>({
    mutationFn: (id) => request(`/deanery-documents/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: LIST_KEY }),
  });
}
