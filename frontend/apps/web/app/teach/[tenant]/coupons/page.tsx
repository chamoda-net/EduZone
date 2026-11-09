import { Megaphone, Ticket } from "lucide-react";

import type { Schema } from "@eduzone/api-client";
import { api } from "@/lib/api";
import { getMe } from "@/lib/session";
import { mainOrigin } from "@/lib/site";
import { workspaceSlug } from "@/lib/workspace";
import { formatDateTime, formatMoney } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import { Badge, Card, CardTitle, EmptyState, ErrorText, PageHeader } from "@eduzone/ui";

import { CopyCouponLink, CouponToggle, NewCouponForm } from "./forms";

type Coupon = Schema<"CouponOut">;
type CourseRow = Schema<"CourseRow">;

const stateTone = { active: "success", scheduled: "info", expired: "neutral", used_up: "warning", disabled: "neutral" } as const;

/** Coupons for the organization's courses: codes to share, or a public sale price shown to everyone. */
export default async function CouponsPage() {
  const [coupons, courses, me, slug, origin] = await Promise.all([
    api<Coupon[]>("~/coupons"), api<CourseRow[]>("~/courses"), getMe(), workspaceSlug(), mainOrigin(),
  ]);
  const role = me?.workspaces.find((w) => w.slug === slug)?.role;
  const allowAll = role === "owner" || role === "admin";
  const paid = courses.ok ? courses.data.filter((c) => c.pricing_model === "one_time" && c.status !== "archived") : [];
  const slugs = new Map(courses.ok ? courses.data.map((c) => [c.id, { slug: c.slug, published: c.status === "published" }]) : []);

  return (
    <>
      <PageHeader eyebrow={t("shell.console")} title={t("coupons.title")} description={t("coupons.subtitle")} />
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_24rem]">
        <section className="flex min-w-0 flex-col gap-3">
          {!coupons.ok && <ErrorText>{errorText(t, coupons.error)}</ErrorText>}
          {coupons.ok && coupons.data.length === 0 && (
            <EmptyState icon={<Ticket />} title={t("coupons.empty")} body={t("coupons.emptyBody")} />
          )}
          {coupons.ok && coupons.data.length > 0 && (
            <ul className="flex flex-col gap-3">
              {coupons.data.map((k, i) => {
                const course = k.course_id ? slugs.get(k.course_id) : null;
                const live = k.state === "active" || k.state === "scheduled";
                return (
                  <li key={k.id} className="ez-rise rounded-ez-lg border border-border bg-surface p-4 shadow-ez-sm sm:p-5"
                      style={{ "--i": i } as React.CSSProperties}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="flex min-w-0 flex-col gap-1.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-ez border border-dashed border-brand/40 bg-brand-50 px-2.5 py-1 font-mono text-sm font-bold tracking-wider text-brand">
                            {k.code}
                          </span>
                          <Badge tone={stateTone[k.state as keyof typeof stateTone] ?? "neutral"} dot>
                            {t(`coupons.state.${k.state as keyof typeof stateTone}`)}
                          </Badge>
                          {k.is_public && (
                            <Badge tone="gold"><Megaphone className="size-3.5" />{t("coupons.sale")}</Badge>
                          )}
                        </div>
                        <p className="font-display text-xl font-semibold">
                          {k.discount_type === "percent"
                            ? t("coupons.percentOff", { percent: (k.percent_bps ?? 0) / 100 })
                            : t("coupons.amountOff", { amount: formatMoney(k.amount_cents ?? 0) })}
                        </p>
                        <p className="truncate text-sm text-muted">{k.course_title ?? t("coupons.allCourses")}</p>
                      </div>
                      <div className="text-right text-sm">
                        <p className="font-semibold tabular-nums">
                          {k.max_redemptions
                            ? t("coupons.usedOf", { used: k.redeemed_count, max: k.max_redemptions })
                            : t("coupons.used", { used: k.redeemed_count })}
                        </p>
                        <p className="text-muted">{t("coupons.until", { date: formatDateTime(k.ends_at) })}</p>
                      </div>
                    </div>
                    {k.max_redemptions ? (
                      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-sunken" aria-hidden>
                        <div className="h-full rounded-full bg-brand" style={{ width: `${Math.min(100, (k.redeemed_count / k.max_redemptions) * 100)}%` }} />
                      </div>
                    ) : null}
                    <div className="mt-3 flex flex-wrap items-center justify-end gap-1 border-t border-border pt-3">
                      {course?.published && live && !k.is_public && (
                        <CopyCouponLink url={`${origin}/course/${course.slug}?coupon=${k.code}`} />
                      )}
                      {k.state !== "expired" && <CouponToggle id={k.id} active={k.status === "active"} />}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
        <Card className="lg:sticky lg:top-6">
          <CardTitle>{t("coupons.new")}</CardTitle>
          {paid.length === 0 && !allowAll ? (
            <p className="text-sm text-muted">{t("coupons.noCourses")}</p>
          ) : (
            <NewCouponForm courses={paid.map((c) => ({ id: c.id, title: c.title }))} allowAll={allowAll} />
          )}
        </Card>
      </div>
    </>
  );
}
