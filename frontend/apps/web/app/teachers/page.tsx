import { ChevronRight, Users } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { SiteShell } from "@/components/shell";
import { TeacherAvatar } from "@/components/teacher-avatar";
import { market } from "@/lib/market";
import { t } from "@eduzone/lib/i18n";
import type { TeacherOut } from "@eduzone/lib/types";
import { Badge, PageHeader } from "@eduzone/ui";

export const metadata: Metadata = { title: "Teachers | EduZone", description: "Sri Lankan teachers for Grade 5, O/L and A/L." };

/** Every teacher with a public class. */
export default async function TeachersPage() {
  const teachers = await market<TeacherOut[]>("/teachers");
  return (
    <SiteShell>
      <PageHeader eyebrow={t("market.dir.eyebrow")} title={t("market.dir.teachers")} description={t("market.dir.teachersBody")} />
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 [&>*]:min-w-0">
        {teachers.map((tc, i) => (
          <li key={tc.slug} className="ez-rise" style={{ "--i": i } as React.CSSProperties}>
            <Link href={`/${tc.subjects[0]?.slug ?? "classes"}/${tc.slug}`}
                  className="group flex h-full flex-col gap-4 rounded-ez-lg border border-border bg-surface p-5 shadow-ez-sm transition hover:-translate-y-0.5 hover:shadow-ez">
              <div className="flex items-center gap-4">
                <TeacherAvatar name={tc.display_name} photo={tc.photo_url} size="lg" />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-display text-lg font-semibold">{tc.display_name}</p>
                  {tc.headline && <p className="truncate text-sm text-muted">{tc.headline}</p>}
                </div>
                <ChevronRight className="size-5 text-subtle group-hover:text-brand" />
              </div>
              <div className="flex flex-wrap gap-1.5">
                {tc.subjects.map((s) => <Badge key={s.slug} tone="brand">{s.name}</Badge>)}
              </div>
              <p className="mt-auto flex items-center gap-4 text-xs font-medium text-muted">
                <span>{t("market.teacher.classes", { count: tc.class_count })}</span>
                {tc.students > 0 && <span className="inline-flex items-center gap-1"><Users className="size-3.5" />{t("market.card.students", { count: tc.students })}</span>}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </SiteShell>
  );
}
