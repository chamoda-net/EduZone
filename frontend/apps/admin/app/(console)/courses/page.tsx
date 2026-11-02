import { GraduationCap } from "lucide-react";
import Link from "next/link";

import type { Schema } from "@eduzone/api-client";
import { EmptyState, ErrorText, FilterChips, PageHeader } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatDateTime, formatMoney } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";

type ReviewRow = Schema<"ReviewRow">;

const FILTERS = ["in_review", "published", "archived", "draft"] as const;
type Filter = (typeof FILTERS)[number];

/** Courses waiting for their first-publish review, and the rest by status. */
export default async function CourseReviewsPage({ searchParams }: PageProps<"/courses">) {
  const { status: raw } = await searchParams;
  const status: Filter = FILTERS.includes(raw as Filter) ? (raw as Filter) : "in_review";
  const res = await api<ReviewRow[]>(`/platform/courses?status=${status}`);

  return (
    <>
      <PageHeader title={t("platform.nav.courseReviews")} description={t("platform.courses.body")} />
      <FilterChips items={FILTERS.map((f) => ({
        href: f === "in_review" ? "/courses" : `/courses?status=${f}`,
        label: t(`platform.courses.filter.${f}`),
        active: f === status,
      }))} />
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.length === 0 && (
        <EmptyState icon={<GraduationCap />}
                    title={status === "in_review" ? t("platform.courses.emptyReview") : t("platform.courses.empty")} />
      )}
      {res.ok && res.data.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-ez-lg border border-border bg-surface">
          {res.data.map((c) => (
            <li key={c.id}>
              <Link href={`/courses/${c.id}`} className="flex flex-col gap-1 p-4 hover:bg-sunken/50 md:flex-row md:items-center md:justify-between">
                <div className="min-w-0">
                  <p className="font-medium">{c.title}</p>
                  <p className="truncate text-sm text-muted">
                    {c.tenant_name} · {c.teacher_name}{c.category_name ? ` · ${c.category_name}` : ""} ·{" "}
                    {t("courses.totalLength", {
                      lectures: t("courses.lectures", { count: c.lecture_count }),
                      minutes: Math.round(c.total_video_seconds / 60),
                    })}
                  </p>
                </div>
                <div className="flex shrink-0 flex-col items-start gap-0.5 text-sm md:items-end">
                  <span className="font-medium tabular-nums">
                    {c.pricing_model === "free" || !c.one_time_price_cents ? t("courses.pricingFree")
                      : formatMoney(c.one_time_price_cents, c.currency)}
                  </span>
                  {c.submitted_at && (
                    <span className="text-xs text-muted">{t("platform.courses.submitted", { date: formatDateTime(c.submitted_at) })}</span>
                  )}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
