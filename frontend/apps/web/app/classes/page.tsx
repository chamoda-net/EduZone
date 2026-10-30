import { ArrowRight, SearchX, SlidersHorizontal } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { MarketClassCard } from "@/components/market-card";
import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { errorText, t } from "@eduzone/lib/i18n";
import type { MarketClassPage, SubjectOut } from "@eduzone/lib/types";
import { Button, Dialog, EmptyState, ErrorText, Field, Input, PageHeader, Select, buttonStyles } from "@eduzone/ui";

export const metadata: Metadata = { title: "Classes | EduZone", description: "Find online classes for Grade 5, O/L and A/L." };

const FILTERS = ["q", "exam", "subject", "year", "medium", "format", "max_fee", "sort", "org"] as const;
type Filters = Partial<Record<(typeof FILTERS)[number], string>>;

/** The catalogue: every listed class, with search and filters (all in the URL, so links can be shared). */
export default async function CatalogPage({ searchParams }: PageProps<"/classes">) {
  const sp = await searchParams;
  const filters: Filters = {};
  for (const key of FILTERS) {
    const v = sp[key];
    if (typeof v === "string" && v.trim()) filters[key] = v.trim();
  }
  const query = new URLSearchParams({ ...filters, limit: "24" });
  if (filters.max_fee) query.set("max_fee", String(Math.round(Number(filters.max_fee) * 100)));
  if (typeof sp.cursor === "string") query.set("cursor", sp.cursor);
  const [res, subjects] = await Promise.all([
    api<MarketClassPage>(`/market/classes?${query}`, { token: null }),
    api<SubjectOut[]>("/market/subjects", { token: null }),
  ]);
  const subjectList = subjects.ok ? subjects.data : [];
  const active = Object.keys(filters).filter((k) => k !== "sort").length;

  const form = <FilterForm filters={filters} subjects={subjectList} />;
  const nextHref = res.ok && res.data.next_cursor
    ? `/classes?${new URLSearchParams({ ...filters, cursor: res.data.next_cursor })}` : null;

  return (
    <SiteShell>
      <PageHeader
        eyebrow={t("market.catalog.eyebrow")}
        title={filters.q ? t("market.catalog.resultsFor", { q: filters.q }) : t("market.catalog.title")}
        description={res.ok ? t("market.catalog.count", { count: res.data.total }) : undefined}
        actions={
          <div className="lg:hidden">
            <Dialog
              title={t("market.filters.title")}
              trigger={
                <Button variant="secondary" icon={<SlidersHorizontal className="size-4" />}>
                  {t("market.filters.title")}{active > 0 && ` · ${active}`}
                </Button>
              }
            >
              {form}
            </Dialog>
          </div>
        }
      />

      <div className="grid gap-8 lg:grid-cols-[260px_1fr] [&>*]:min-w-0">
        <aside className="hidden lg:block">
          <div className="sticky top-24 rounded-ez-lg border border-border bg-surface p-5 shadow-ez-sm">{form}</div>
        </aside>
        <div className="flex flex-col gap-6">
          {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
          {res.ok && res.data.items.length === 0 && (
            <EmptyState
              icon={<SearchX />}
              title={t("market.catalog.empty")}
              body={t("market.catalog.emptyBody")}
              action={<Link href="/classes" className={buttonStyles("secondary")}>{t("market.filters.clear")}</Link>}
            />
          )}
          {res.ok && res.data.items.length > 0 && (
            <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
              {res.data.items.map((c, i) => <MarketClassCard key={c.id} c={c} index={i} />)}
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
    </SiteShell>
  );
}

function FilterForm({ filters, subjects }: { filters: Filters; subjects: SubjectOut[] }) {
  const years = Array.from({ length: 6 }, (_, i) => 2025 + i);
  return (
    <form action="/classes" className="flex flex-col gap-4">
      {filters.org && <input type="hidden" name="org" value={filters.org} />}
      <Field label={t("market.search.label")}>
        <Input name="q" defaultValue={filters.q} placeholder={t("market.search.placeholder")} />
      </Field>
      <Field label={t("account.exam")}>
        <Select name="exam" defaultValue={filters.exam ?? ""}>
          <option value="">{t("market.filters.any")}</option>
          {(["grade_5", "ol", "al", "other"] as const).map((e) => <option key={e} value={e}>{t(`exam.${e}`)}</option>)}
        </Select>
      </Field>
      <Field label={t("market.filters.subject")}>
        <Select name="subject" defaultValue={filters.subject ?? ""}>
          <option value="">{t("market.filters.any")}</option>
          {subjects.map((s) => <option key={s.slug} value={s.slug}>{s.name}</option>)}
        </Select>
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label={t("market.filters.year")}>
          <Select name="year" defaultValue={filters.year ?? ""}>
            <option value="">{t("market.filters.any")}</option>
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </Select>
        </Field>
        <Field label={t("market.filters.medium")}>
          <Select name="medium" defaultValue={filters.medium ?? ""}>
            <option value="">{t("market.filters.any")}</option>
            {(["si", "ta", "en"] as const).map((m) => <option key={m} value={m}>{t(`medium.${m}`)}</option>)}
          </Select>
        </Field>
      </div>
      <Field label={t("market.filters.format")}>
        <Select name="format" defaultValue={filters.format ?? ""}>
          <option value="">{t("market.filters.any")}</option>
          <option value="live">{t("market.card.live")}</option>
          <option value="recorded">{t("market.card.recorded")}</option>
        </Select>
      </Field>
      <Field label={t("market.filters.maxFee")}>
        <Input name="max_fee" type="number" inputMode="numeric" min={0} step={100} defaultValue={filters.max_fee} />
      </Field>
      <Field label={t("market.filters.sort")}>
        <Select name="sort" defaultValue={filters.sort ?? "popular"}>
          <option value="popular">{t("market.filters.sortPopular")}</option>
          <option value="newest">{t("market.filters.sortNewest")}</option>
          <option value="price">{t("market.filters.sortPrice")}</option>
        </Select>
      </Field>
      <div className="flex gap-2">
        <Button className="flex-1">{t("market.filters.apply")}</Button>
        <Link href="/classes" className={buttonStyles("ghost")}>{t("market.filters.clear")}</Link>
      </div>
    </form>
  );
}
