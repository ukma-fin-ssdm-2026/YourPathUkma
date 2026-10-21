// Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: documents.test.tsx.
import type { CSSProperties } from "react";
import { Link } from "react-router";
import type { NormativeCourse } from "../../api/types";
import { formatCredits } from "../../lib/credits";
import { trimesterLabel } from "../../lib/trimester";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { linkButtonClass } from "../../ui/linkButton";

export function NormativePanel({
  courses,
  year,
}: {
  courses: NormativeCourse[] | null;
  year: number;
}) {
  const total = (courses ?? []).reduce((sum, course) => sum + course.credits, 0);
  return (
    <section aria-labelledby="normative-title">
      <Card className="grid gap-3">
        <h2 id="normative-title" className="font-display text-base">
          Розпізнані нормативні
        </h2>
        {courses === null ? (
          <p className="text-ink-2">
            Після розпізнавання тут з'являться нормативні дисципліни з вашого документа.
          </p>
        ) : (
          <>
            <p className="text-sm text-ink-2">З вибраного документа. Їх не можна змінити.</p>
            <table className="w-full border-collapse text-left">
              <tbody>
                {courses.map((course, index) => (
                  <tr
                    key={`${course.raw_title}-${course.trimester}`}
                    className="rise border-b border-rule"
                    style={{ "--i": index } as CSSProperties}
                  >
                    <td className="py-2 pr-2">
                      <span className="break-words">{course.raw_title}</span>
                      <small className="block text-[13px] text-ink-2">
                        {trimesterLabel(course.trimester)}
                        {course.course_id === null && " · немає в каталозі"}
                      </small>
                    </td>
                    <td className="py-2 text-right font-semibold tabular-nums">
                      {formatCredits(course.credits)}
                    </td>
                  </tr>
                ))}
                <tr>
                  <td className="py-2 font-semibold">Разом</td>
                  <td className="py-2 text-right font-semibold tabular-nums">{formatCredits(total)}</td>
                </tr>
              </tbody>
            </table>
          </>
        )}
        {courses === null ? (
          <Button disabled>Далі: до побажань</Button>
        ) : (
          <Link
            to={`/path/create/preferences?year=${year}`}
            className={linkButtonClass + " text-center"}
          >
            Далі: до побажань
          </Link>
        )}
      </Card>
    </section>
  );
}
