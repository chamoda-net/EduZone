import Link from "next/link";

import { ClassCard } from "@/components/class-card";
import { StudentHeader } from "@/components/student-header";
import { ErrorText, buttonClass } from "@eduzone/ui";
import { api } from "@/lib/api";
import { errorText, t } from "@eduzone/lib/i18n";
import { getBranding } from "@/lib/session";
import type { ClassItem, PublicClassPage } from "@eduzone/lib/types";

type Exam = NonNullable<ClassItem["exam"]>;
const EXAMS: Exam[] = ["al", "ol", "grade_5", "other"];

/** The tenant's public home: its published classes, open to anyone. */
export default async function Home({ searchParams }: PageProps<"/">) {
  const sp = await searchParams;
  const exam = EXAMS.includes(sp.exam as Exam) ? (sp.exam as Exam) : null;
  const cursor = typeof sp.cursor === "string" ? sp.cursor : null;
  const q = new URLSearchParams({ limit: "24" });
  if (exam) q.set("exam", exam);
  if (cursor) q.set("cursor", cursor);
  const [branding, res] = await Promise.all([getBranding(), api<PublicClassPage>(`/public/classes?${q}`, { token: null })]);

  return (
    <>
      <StudentHeader />
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-4 py-8">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          {t("app.tagline", { org: branding?.name ?? "" })}
        </h1>

        <div className="flex gap-2 overflow-x-auto">
          {[null, ...EXAMS].map((e) => (
            <Link
              key={e ?? "all"}
              href={e ? `/?exam=${e}` : "/"}
              className={`rounded-full border px-3 py-1.5 text-sm whitespace-nowrap ${
                e === exam ? "border-brand bg-brand text-on-brand" : "border-border bg-surface"
              }`}
            >
              {e ? t(`exam.${e}`) : t("classes.filter.all")}
            </Link>
          ))}
        </div>

        {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
        {res.ok && res.data.items.length === 0 && <p className="text-muted">{t("catalog.empty")}</p>}
        {res.ok && res.data.items.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2">
            {res.data.items.map((c) => (
              <ClassCard key={c.id} c={c} />
            ))}
          </div>
        )}
        {res.ok && res.data.next_cursor && (
          <Link
            href={`/?${new URLSearchParams({ ...(exam ? { exam } : {}), cursor: res.data.next_cursor })}`}
            className={`${buttonClass.link} self-end`}
          >
            {t("classes.loadMore")}
          </Link>
        )}
      </main>
      <footer className="px-4 py-6 text-center text-xs text-muted">{t("app.poweredBy")}</footer>
    </>
  );
}
