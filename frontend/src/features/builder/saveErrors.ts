// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: save.test.tsx.
import { fieldErrors, type ApiError } from "../../api/errors";
import type { PlanItem } from "../../api/types";
import { ERROR_TEXT } from "./SummaryStrip";

const ITEM_TEXT: Record<string, string> = {
  COURSE_NOT_FOUND: "Дисципліни немає в каталозі",
  COURSE_DATA_MISMATCH: "Кредити або триместр не збігаються з каталогом",
  NORMATIVE_NOT_ALLOWED: "Нормативну дисципліну додає деканат",
};

const CODE_TEXT: Record<string, string> = {
  PLAN_NOT_EDITABLE: "Цей план уже подано, редагувати його не можна",
  PLAN_NOT_SUBMITTABLE: "Подати можна лише чернетку",
};

/** Текст для коду з відповіді сервера; лише власні ключі таблиці, щоб "constructor" чи "__proto__" не читали прототип. */
function textFor(table: Record<string, string>, code: string | undefined): string | undefined {
  return code !== undefined && Object.hasOwn(table, code) ? table[code] : undefined;
}

/** Бекенд пише помилки плану як «КОД: текст». Відомий код перекладаємо, в іншому прибираємо префікс. */
function planMessage(message: string): string {
  const match = /^([A-Z_]+): (.*)$/s.exec(message);
  return match ? (textFor(ERROR_TEXT, match[1]) ?? match[2]!) : message;
}

export interface SaveErrors {
  /** Повідомлення біля карток, за course_id. */
  itemErrors: Record<number, string>;
  /** Повідомлення над планом. */
  form: string[];
}

/** Перетворює відповідь сервера на повідомлення, які можна показати біля карток і над планом. */
export function describeSaveError(error: ApiError, items: PlanItem[]): SaveErrors {
  const known = textFor(CODE_TEXT, error.code);
  if (known) return { itemErrors: {}, form: [known] };

  if (error.status === 422 && error.details.length > 0) {
    const itemErrors: Record<number, string> = {};
    const rest = [];
    for (const detail of error.details) {
      const match = /^items\.(\d+)\./.exec(detail.field);
      const item = match ? items[Number(match[1])] : undefined;
      const text = textFor(ITEM_TEXT, /^([A-Z_]+):/.exec(detail.message)?.[1]);
      if (item && text) itemErrors[item.course_id] = text;
      else rest.push(detail);
    }
    return {
      itemErrors,
      form: fieldErrors(rest).form.concat(
        rest.filter((d) => d.field && d.field !== "body").map((d) => planMessage(d.message)),
      ),
    };
  }
  return { itemErrors: {}, form: [error.message] };
}
