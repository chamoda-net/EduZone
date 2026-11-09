import type { Metadata } from "next";
import Link from "next/link";

import type { Schema } from "@eduzone/api-client";
import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { t } from "@eduzone/lib/i18n";
import { PageHeader } from "@eduzone/ui";

import { CourseCatalog, readFilters } from "./catalog";

type Category = Schema<"CourseCategoryOut">;

export const metadata: Metadata = {
  title: "Courses | EduZone",
  description: "Self-paced video courses with lifetime access, from teachers across Sri Lanka.",
};

/** Every course on the marketplace, with search and filters. */
export default async function CoursesPage({ searchParams }: PageProps<"/courses">) {
  const sp = await searchParams;
  const filters = readFilters(sp);
  const cats = await api<Category[]>("/market/courses/categories", { token: null });
  const categories = cats.ok ? cats.data : [];
  const tops = categories.filter((c) => c.parent_id === null && c.course_count > 0);

  return (
    <SiteShell>
      <CourseCatalog
        basePath="/courses"
        filters={filters}
        cursor={typeof sp.cursor === "string" ? sp.cursor : undefined}
        categories={categories}
        header={(count, filterButton) => (
          <div className="flex flex-col gap-5">
            <PageHeader
              eyebrow={t("market.courses.eyebrow")}
              title={filters.q ? t("market.courses.resultsFor", { q: filters.q }) : t("market.courses.title")}
              description={count !== null ? `${t("market.courses.count", { count })} · ${t("market.courses.lead")}` : t("market.courses.lead")}
              actions={filterButton}
            />
            {tops.length > 0 && (
              <nav aria-label={t("market.home.courseCategories")} className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 [scrollbar-width:none] sm:mx-0 sm:px-0">
                {tops.map((c) => (
                  <Link key={c.slug} href={`/courses/${c.slug}`}
                        className="inline-flex min-h-10 shrink-0 items-center gap-2 rounded-full border border-border-strong bg-surface px-4 text-sm font-semibold whitespace-nowrap text-muted transition hover:border-foreground/40 hover:text-foreground">
                    {c.name_en}
                    <span className="rounded-full bg-sunken px-1.5 text-xs tabular-nums">{c.course_count}</span>
                  </Link>
                ))}
              </nav>
            )}
          </div>
        )}
      />
    </SiteShell>
  );
}
