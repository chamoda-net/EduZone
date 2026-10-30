import { BookOpen } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { ClassCard } from "@/components/class-card";
import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { getMe } from "@/lib/session";
import { errorText, t } from "@eduzone/lib/i18n";
import type { MyClass } from "@eduzone/lib/types";
import { Badge, EmptyState, ErrorText, PageHeader, buttonStyles } from "@eduzone/ui";

export default async function MyClassesPage() {
  const me = await getMe();
  if (!me) redirect("/login?next=/learn/classes");
  const res = await api<MyClass[]>("/learn/classes");
  const first = me.full_name.split(/\s+/)[0];

  return (
    <SiteShell>
      <PageHeader eyebrow={t("my.eyebrow")} title={t("my.greeting", { name: first })} description={t("my.subtitle")} />
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.length === 0 && (
        <EmptyState
          icon={<BookOpen />}
          title={t("my.empty")}
          body={t("my.emptyBody")}
          action={<Link href="/" className={buttonStyles("primary")}>{t("my.browse")}</Link>}
        />
      )}
      {res.ok && res.data.length > 0 && (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {res.data.map((m, i) => (
            <ClassCard
              key={m.class.id}
              c={m.class}
              href={`/learn/classes/${m.class.id}`}
              index={i}
              footer={
                <Badge tone={m.unlocked_months > 0 ? "success" : "neutral"} dot>
                  {t("my.unlocked", { count: m.unlocked_months })}
                </Badge>
              }
            />
          ))}
        </div>
      )}
    </SiteShell>
  );
}
