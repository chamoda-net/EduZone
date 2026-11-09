import { ArrowRight, SearchX, SlidersHorizontal } from "lucide-react";
import Link from "next/link";

import type { Schema } from "@eduzone/api-client";
import { CourseCard } from "@/components/course-card";
import { api } from "@/lib/api";
import { COURSE_SORTS, LENGTHS, LEVELS } from "@/lib/courses";
import { errorText, t } from "@eduzone/lib/i18n";
import { Button, Dialog, EmptyState, ErrorText, Field, Input, Select, buttonStyles } from "@eduzone/ui";

type CoursePage = Schema<"MarketCoursePage">;
type Category = Schema<"CourseCategoryOut">;

const FILTERS = ["q", "category", "level", "language", "price", "max_price", "rating", "length", "sort"] as const;
export type CourseFilters = Partial<Record<(typeof FILTERS)[number], string>>;

export function readFilters(sp: Record<string, string | string[] | undefined>): CourseFilters {
  const out: CourseFilters = {};
  for (const key of FILTERS) {
    const v = sp[key];
    if (typeof v === "string" && v.trim()) out[key] = v.trim();
  }
  return out;
}

/** The course grid with its filters. `basePath` is where the filter form submits (/courses or a category page);
 * a category page passes its category so it stays fixed. Every filter lives in the URL. */
export async function CourseCatalog({ basePath, filters, cursor, categories, fixedCategory, header }: {
  basePath: string;
  filters: CourseFilters;
  cursor?: string;
  categories: Category[];
  fixedCategory?: string;
  header: (count: number | null, filterButton: React.ReactNode) => React.ReactNode;
}) {
  const query = new URLSearchParams({ ...filters, limit: "24" });
  if (fixedCategory) query.set("category", fixedCategory);
  if (filters.max_price) query.set("max_price", String(Math.round(Number(filters.max_price) * 100)));
  if (cursor) query.set("cursor", cursor);
  const res = await api<CoursePage>(`/market/courses?${query}`, { token: null });
  const active = Object.keys(filters).filter((k) => k !== "sort").length;
  const form = <FilterForm basePath={basePath} filters={filters} categories={categories} fixedCategory={fixedCategory} />;
  const nextHref = res.ok && res.data.next_cursor
    ? `${basePath}?${new URLSearchParams({ ...filters, cursor: res.data.next_cursor })}` : null;
  const filterButton = (
    <div className="lg:hidden">
      <Dialog title={t("market.filters.title")} trigger={
        <Button variant="secondary" icon={<SlidersHorizontal className="size-4" />}>
          {t("market.filters.title")}{active > 0 && ` · ${active}`}
        </Button>
      }>
        {form}
      </Dialog>
    </div>
  );

  return (
    <>
      {header(res.ok ? res.data.total : null, filterButton)}
      <div className="grid gap-8 lg:grid-cols-[260px_1fr] [&>*]:min-w-0">
        <aside className="hidden lg:block">
          <div className="sticky top-24 rounded-ez-lg border border-border bg-surface p-5 shadow-ez-sm">{form}</div>
        </aside>
        <div className="flex flex-col gap-6">
          {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
          {res.ok && res.data.items.length === 0 && (
            <EmptyState icon={<SearchX />} title={t("market.courses.empty")} body={t("market.courses.emptyBody")}
                        action={<Link href={basePath} className={buttonStyles("secondary")}>{t("market.filters.clear")}</Link>} />
          )}
          {res.ok && res.data.items.length > 0 && (
            <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
              {res.data.items.map((c, i) => <CourseCard key={c.id} c={c} index={i} />)}
            </div>
          )}
          {nextHref && (
            <Link href={nextHref} className={buttonStyles("secondary", "md", "self-center")}>
              {t("classes.loadMore")}
              <ArrowRight className="size-4" />
            </Link>
          )}
        </div>
      </div>
    </>
  );
}

function FilterForm({ basePath, filters, categories, fixedCategory }: {
  basePath: string; filters: CourseFilters; categories: Category[]; fixedCategory?: string;
}) {
  const tops = categories.filter((c) => c.parent_id === null);
  return (
    <form action={basePath} className="flex flex-col gap-4">
      <Field label={t("market.search.label")}>
        <Input name="q" defaultValue={filters.q} placeholder={t("market.courses.searchPlaceholder")} />
      </Field>
      {!fixedCategory && (
        <Field label={t("market.courses.filter.category")}>
          <Select name="category" defaultValue={filters.category ?? ""}>
            <option value="">{t("market.courses.allCategories")}</option>
            {tops.map((top) => {
              const subs = categories.filter((c) => c.parent_id === top.id);
              return subs.length === 0 ? <option key={top.slug} value={top.slug}>{top.name_en}</option> : (
                <optgroup key={top.slug} label={top.name_en}>
                  <option value={top.slug}>{top.name_en}</option>
                  {subs.map((s) => <option key={s.slug} value={s.slug}>{s.name_en}</option>)}
                </optgroup>
              );
            })}
          </Select>
        </Field>
      )}
      <div className="grid grid-cols-2 gap-3">
        <Field label={t("market.courses.filter.level")}>
          <Select name="level" defaultValue={filters.level ?? ""}>
            <option value="">{t("market.filters.any")}</option>
            {LEVELS.map((l) => <option key={l} value={l}>{t(`courses.level.${l}`)}</option>)}
          </Select>
        </Field>
        <Field label={t("market.courses.filter.language")}>
          <Select name="language" defaultValue={filters.language ?? ""}>
            <option value="">{t("market.filters.any")}</option>
            {(["si", "ta", "en"] as const).map((m) => <option key={m} value={m}>{t(`medium.${m}`)}</option>)}
          </Select>
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label={t("market.courses.filter.price")}>
          <Select name="price" defaultValue={filters.price ?? ""}>
            <option value="">{t("market.filters.any")}</option>
            <option value="free">{t("market.courses.filter.free")}</option>
            <option value="paid">{t("market.courses.filter.paid")}</option>
          </Select>
        </Field>
        <Field label={t("market.courses.filter.rating")}>
          <Select name="rating" defaultValue={filters.rating ?? ""}>
            <option value="">{t("market.filters.any")}</option>
            {["4.5", "4", "3.5"].map((r) => <option key={r} value={r}>{t("market.courses.filter.ratingFrom", { rating: r })}</option>)}
          </Select>
        </Field>
      </div>
      <Field label={t("market.courses.filter.length")}>
        <Select name="length" defaultValue={filters.length ?? ""}>
          <option value="">{t("market.filters.any")}</option>
          {LENGTHS.map((l) => <option key={l} value={l}>{t(`market.courses.length.${l}`)}</option>)}
        </Select>
      </Field>
      <Field label={t("market.courses.filter.maxPrice")}>
        <Input name="max_price" type="number" inputMode="numeric" min={0} step={100} defaultValue={filters.max_price} />
      </Field>
      <Field label={t("market.filters.sort")}>
        <Select name="sort" defaultValue={filters.sort ?? "popular"}>
          {COURSE_SORTS.map((s) => <option key={s} value={s}>{t(`market.courses.sort.${s}`)}</option>)}
        </Select>
      </Field>
      <div className="flex gap-2">
        <Button className="flex-1">{t("market.courses.filter.apply")}</Button>
        <Link href={basePath} className={buttonStyles("ghost")}>{t("market.filters.clear")}</Link>
      </div>
    </form>
  );
}
