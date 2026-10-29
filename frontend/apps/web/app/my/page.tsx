import Link from "next/link";
import { redirect } from "next/navigation";

import { ClassCard } from "@/components/class-card";
import { StudentHeader } from "@/components/student-header";
import { ErrorText, buttonClass } from "@eduzone/ui";
import { api } from "@/lib/api";
import { errorText, t } from "@eduzone/lib/i18n";
import { getMe } from "@/lib/session";
import type { MyClass } from "@eduzone/lib/types";

export default async function MyClassesPage() {
  if (!(await getMe())) redirect("/login?next=/my");
  const res = await api<MyClass[]>("/student/classes");

  return (
    <>
      <StudentHeader />
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-5 px-4 py-8">
        <h1 className="text-2xl font-semibold">{t("my.title")}</h1>
        {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
        {res.ok && res.data.length === 0 && (
          <div className="flex flex-col items-start gap-3">
            <p className="text-muted">{t("my.empty")}</p>
            <Link href="/" className={buttonClass.primary}>{t("my.browse")}</Link>
          </div>
        )}
        {res.ok && res.data.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2">
            {res.data.map((m) => (
              <ClassCard
                key={m.class.id}
                c={m.class}
                footer={<p className="text-sm text-muted">{t("my.unlocked", { count: m.unlocked_months })}</p>}
              />
            ))}
          </div>
        )}
      </main>
    </>
  );
}
