import Link from "next/link";
import { notFound } from "next/navigation";

import type { Schema } from "@eduzone/api-client";
import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { market } from "@/lib/market";
import { t } from "@eduzone/lib/i18n";
import { PageHeader, cx } from "@eduzone/ui";

import { CourseCatalog, readFilters } from "./catalog";

type CategoryPage = Schema<"CourseCategoryPage">;
type Category = Schema<"CourseCategoryOut">;

export const categoryPage = (slug: string) => market<CategoryPage>(`/courses/categories/${slug}`);

/** /courses/<category> and /courses/<category>/<sub>: the category's courses, its subcategories as chips. */
export async function CategoryView({ path, sp }: {
  path: string[];
  sp: Record<string, string | string[] | undefined>;
}) {
  const slug = path.at(-1) as string;
  const page = await categoryPage(slug);
  // A subcategory lives under its parent's address, and a top category at the top level only.
  const expected = page.parent ? [page.parent.slug, page.category.slug] : [page.category.slug];
  if (expected.join("/") !== path.join("/")) notFound();
  const cats = await api<Category[]>("/market/courses/categories", { token: null });
  const top = page.parent ?? page.category;
  const chips = (cats.ok ? cats.data : []).filter((c) => c.parent_id === top.id && c.course_count > 0);
  const basePath = `/courses/${path.join("/")}`;
  const filters = readFilters(sp);
  delete filters.category;

  return (
    <SiteShell>
      <CourseCatalog
        basePath={basePath}
        filters={filters}
        cursor={typeof sp.cursor === "string" ? sp.cursor : undefined}
        categories={cats.ok ? cats.data : []}
        fixedCategory={page.category.slug}
        header={(count, filterButton) => (
          <div className="flex flex-col gap-5">
            <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-1.5 text-sm text-muted">
              <Link href="/courses" className="hover:text-foreground hover:underline">{t("market.course.breadcrumb")}</Link>
              {page.parent && (
                <>
                  <span aria-hidden>/</span>
                  <Link href={`/courses/${page.parent.slug}`} className="hover:text-foreground hover:underline">{page.parent.name_en}</Link>
                </>
              )}
            </nav>
            <PageHeader
              title={t("market.category.title", { name: page.category.name_en })}
              description={count !== null ? `${t("market.courses.count", { count })} · ${t("market.category.lead", { name: page.category.name_en })}` : undefined}
              actions={filterButton}
            />
            {chips.length > 0 && (
              <nav aria-label={t("market.courses.topics")} className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 [scrollbar-width:none] sm:mx-0 sm:px-0">
                {[top, ...chips].map((c) => {
                  const href = c.id === top.id ? `/courses/${top.slug}` : `/courses/${top.slug}/${c.slug}`;
                  const active = c.id === page.category.id;
                  return (
                    <Link key={c.slug} href={href} aria-current={active ? "true" : undefined}
                          className={cx("inline-flex min-h-10 shrink-0 items-center rounded-full border px-4 text-sm font-semibold whitespace-nowrap transition",
                                        active ? "border-brand-800 bg-brand-800 text-on-brand" : "border-border-strong bg-surface text-muted hover:text-foreground")}>
                      {c.id === top.id ? t("market.courses.allCategories") : c.name_en}
                    </Link>
                  );
                })}
              </nav>
            )}
          </div>
        )}
      />
    </SiteShell>
  );
}
