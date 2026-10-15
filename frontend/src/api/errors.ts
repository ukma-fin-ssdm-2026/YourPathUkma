// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: client.test.ts, lib.test.ts.
export interface ErrorDetail {
  field: string;
  message: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ErrorDetail[];
  readonly requestId: string | null;

  constructor(
    status: number,
    code: string,
    message: string,
    details: ErrorDetail[] = [],
    requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

const VALUE_ERROR_PREFIX = "Value error, ";

/** Розкладає `details` 422: помилки полів окремо, правила рівня всього тіла (field `body` або порожнє) у `form`. */
export function fieldErrors(details: ErrorDetail[]): {
  fields: Record<string, string>;
  form: string[];
} {
  const fields: Record<string, string> = {};
  const form: string[] = [];
  for (const detail of details) {
    const message = detail.message.startsWith(VALUE_ERROR_PREFIX)
      ? detail.message.slice(VALUE_ERROR_PREFIX.length)
      : detail.message;
    if (!detail.field || detail.field === "body") form.push(message);
    else fields[detail.field] = message;
  }
  return { fields, form };
}
