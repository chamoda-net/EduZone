import { MessageSquareText, Star } from "lucide-react";
import Link from "next/link";

import type { Schema } from "@eduzone/api-client";
import { ActionButton } from "@eduzone/ui/action-button";
import { Badge, EmptyState, ErrorText, FilterChips, PageHeader } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";

import { showReview } from "../../actions";
import { HideForm } from "./hide-form";

const FILTERS = ["all", "visible", "hidden"] as const;
type Filter = (typeof FILTERS)[number];

/** Course reviews across the marketplace, newest first; hide one with a reason, or show it again. */
export default async function CourseReviewsPage({ searchParams }: PageProps<"/course-reviews">) {
  const { status: raw } = await searchParams;
  const status: Filter = FILTERS.includes(raw as Filter) ? (raw as Filter) : "all";
  const res = await api<Schema<"StaffReview">[]>(`/platform/course-reviews${status === "all" ? "" : `?status=${status}`}`);
  return (
    <>
      <PageHeader title={t("platform.nav.courseReviewsMod")} description={t("platform.reviews.body")} />
      <FilterChips items={FILTERS.map((f) => ({
        href: f === "all" ? "/course-reviews" : `/course-reviews?status=${f}`, label: t(`platform.reviews.filter.${f}`), active: f === status,
      }))} />
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.length === 0 && <EmptyState icon={<MessageSquareText />} title={t("platform.reviews.empty")} />}
      {res.ok && res.data.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-ez-lg border border-border bg-surface">
          {res.data.map((r) => (
            <li key={r.id} className="flex flex-col gap-2 p-4">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="inline-flex items-center gap-0.5 font-semibold text-gold-strong">
                  {r.rating}<Star className="size-3.5 fill-gold text-gold" />
                </span>
                <Link href={`/courses/${r.course_id}`} className="font-semibold text-brand hover:underline">{r.course_title}</Link>
                <span className="text-muted">· {r.tenant_name} · {r.reviewer} · {formatDateTime(r.created_at)}</span>
                {r.status === "hidden" && <Badge tone="warning">{t("platform.reviews.hidden", { reason: r.hidden_reason ?? "" })}</Badge>}
              </div>
              {r.comment && <p className="text-sm whitespace-pre-line">{r.comment}</p>}
              {r.status === "visible"
                ? <HideForm reviewId={r.id} />
                : <div><ActionButton small action={showReview.bind(null, r.id)} label={t("platform.reviews.show")} done={t("platform.reviews.done")} /></div>}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
