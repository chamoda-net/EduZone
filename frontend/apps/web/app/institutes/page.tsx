import { Building2, ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { SiteShell } from "@/components/shell";
import { market } from "@/lib/market";
import { t } from "@eduzone/lib/i18n";
import type { InstituteOut } from "@eduzone/lib/types";
import { EmptyState, PageHeader } from "@eduzone/ui";

export const metadata: Metadata = { title: "Institutes | EduZone", description: "Tuition institutes teaching on EduZone." };

export default async function InstitutesPage() {
  const institutes = await market<InstituteOut[]>("/institutes");
  return (
    <SiteShell>
      <PageHeader eyebrow={t("market.dir.eyebrow")} title={t("market.dir.institutes")} description={t("market.dir.institutesBody")} />
      {institutes.length === 0 && <EmptyState icon={<Building2 />} title={t("market.dir.noInstitutes")} />}
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 [&>*]:min-w-0">
        {institutes.map((inst, i) => (
          <li key={inst.slug} className="ez-rise" style={{ "--i": i } as React.CSSProperties}>
            <Link href={`/institutes/${inst.slug}`}
                  className="group flex h-full items-center gap-4 rounded-ez-lg border border-border bg-surface p-5 shadow-ez-sm transition hover:-translate-y-0.5 hover:shadow-ez">
              <span className="grid size-14 shrink-0 place-items-center rounded-ez bg-brand-900 text-gold"><Building2 className="size-6" /></span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-display text-lg font-semibold">{inst.name}</p>
                <p className="truncate text-sm text-muted">{inst.subjects.join(" · ")}</p>
                <p className="text-xs text-muted">{t("market.institute.counts", { classes: inst.class_count, teachers: inst.teacher_count })}</p>
              </div>
              <ChevronRight className="size-5 text-subtle group-hover:text-brand" />
            </Link>
          </li>
        ))}
      </ul>
    </SiteShell>
  );
}
