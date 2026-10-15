// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: export.test.tsx.
import { useMutation } from "@tanstack/react-query";
import { requestBlob } from "../../api/client";
import type { ApiError } from "../../api/errors";
import { saveBlob } from "../../lib/download";

/** Завантажує PDF плану й зберігає його файлом; повертає ім'я збереженого файлу. */
export function useExportPlan() {
  return useMutation<string, ApiError, { id: number; academicYear: number }>({
    mutationFn: async ({ id, academicYear }) => {
      const { blob, filename } = await requestBlob(`/plans/${id}/export`, { query: { format: "pdf" } });
      const name = filename ?? `plan-${academicYear}.pdf`;
      saveBlob(blob, name);
      return name;
    },
  });
}
