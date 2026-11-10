import { CheckCircle2, Heart, Star, Users } from "lucide-react";

import type { Schema } from "@eduzone/api-client";
import { formatMoney, formatMonth } from "@eduzone/lib/format";
import { t } from "@eduzone/lib/i18n";
import { Card, CardTitle, FilterChips, StatTile } from "@eduzone/ui";

type Insights = Schema<"CourseInsights">;

export const INSIGHT_RANGES = ["3", "6", "12"] as const;

/** The course's numbers: who has it, who finished, ratings and saves; money and enrolments per month; coupons. */
export function CourseInsightsView({ d, href, range }: { d: Insights; href: (months: string) => string; range: string }) {
  const money = (cents: number) => formatMoney(cents, d.currency);
  const top = Math.max(1, ...d.months.map((m) => m.gross_cents));
  const enrolTop = Math.max(1, ...d.months.map((m) => m.enrol_paid + m.enrol_coupon + m.enrol_free));
  const T = d.totals;

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <StatTile icon={<Users />} label={t("insights.students")} value={String(d.students)} hint={t("insights.studentsHint")} />
        <StatTile icon={<CheckCircle2 />} label={t("insights.completion")} value={`${d.completion_rate}%`}
                  hint={t("insights.completionHint", { done: d.completed_students, total: d.students })} />
        <StatTile tone="gold" icon={<Star />} label={t("insights.rating")}
                  value={d.rating_avg != null && d.rating_count > 0 ? d.rating_avg.toFixed(1) : "—"}
                  hint={t("insights.ratings", { count: d.rating_count })} />
        <StatTile icon={<Heart />} label={t("insights.saved")} value={String(d.wishlist_count)} hint={t("insights.savedHint")} />
      </div>

      <FilterChips label={t("insights.range")} items={INSIGHT_RANGES.map((r) => ({
        href: href(r), label: t("insights.months", { count: Number(r) }), active: r === range,
      }))} />

      <Card className="flex flex-col gap-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <CardTitle>{t("insights.revenue")}</CardTitle>
          <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
            <div><dt className="text-muted">{t("insights.gross")}</dt><dd className="font-display text-xl font-semibold tabular-nums">{money(T.gross_cents)}</dd></div>
            <div><dt className="text-muted">{t("insights.refunds")}</dt><dd className="font-display text-xl font-semibold text-danger tabular-nums">{money(T.refunds_cents)}</dd></div>
            <div><dt className="text-muted">{t("insights.net")}</dt><dd className="font-display text-xl font-semibold text-brand tabular-nums">{money(T.net_cents)}</dd></div>
          </dl>
        </div>
        {/* Bars: gross per month, the organization's net inside it. The table below has the same numbers. */}
        <div className="flex h-44 items-end gap-1.5 border-b border-border sm:gap-2.5" aria-hidden>
          {d.months.map((m) => (
            <div key={m.month} className="group relative flex h-full flex-1 flex-col justify-end" title={`${formatMonth(m.month)}: ${money(m.gross_cents)}`}>
              <div className="relative w-full overflow-hidden rounded-t-[5px] bg-brand-100 transition group-hover:bg-brand-200"
                   style={{ height: `${(m.gross_cents / top) * 100}%`, minHeight: m.gross_cents ? 3 : 0 }}>
                <div className="absolute inset-x-0 bottom-0 bg-brand" style={{ height: m.gross_cents ? `${Math.max(0, m.net_cents / m.gross_cents) * 100}%` : 0 }} />
              </div>
            </div>
          ))}
        </div>
        <div className="flex gap-1.5 text-[0.7rem] text-muted sm:gap-2.5" aria-hidden>
          {d.months.map((m) => (
            <span key={m.month} className="flex-1 truncate text-center">{new Date(`${m.month}T00:00:00`).toLocaleDateString("en", { month: "short" })}</span>
          ))}
        </div>
        <p className="flex flex-wrap gap-4 text-xs text-muted">
          <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-brand-100" />{t("insights.gross")}</span>
          <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-brand" />{t("insights.netLegend")}</span>
        </p>
      </Card>

      <Card className="flex flex-col gap-4">
        <CardTitle>{t("insights.enrolments")}</CardTitle>
        <div className="flex h-28 items-end gap-1.5 sm:gap-2.5" aria-hidden>
          {d.months.map((m) => {
            const total = m.enrol_paid + m.enrol_coupon + m.enrol_free;
            return (
              <div key={m.month} className="flex h-full flex-1 flex-col justify-end" title={`${formatMonth(m.month)}: ${total}`}>
                <div className="flex w-full flex-col-reverse overflow-hidden rounded-t-[5px]" style={{ height: `${(total / enrolTop) * 100}%` }}>
                  <div className="bg-brand" style={{ flex: m.enrol_paid }} />
                  <div className="bg-gold" style={{ flex: m.enrol_coupon }} />
                  <div className="bg-success" style={{ flex: m.enrol_free }} />
                </div>
              </div>
            );
          })}
        </div>
        <p className="flex flex-wrap gap-4 text-xs text-muted">
          <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-brand" />{t("insights.paid", { count: T.enrol_paid })}</span>
          <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-gold" />{t("insights.coupon", { count: T.enrol_coupon })}</span>
          <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-success" />{t("insights.free", { count: T.enrol_free })}</span>
          {T.refund_count > 0 && <span>{t("insights.refundCount", { count: T.refund_count })}</span>}
        </p>
      </Card>

      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[36rem] text-sm">
          <caption className="sr-only">{t("insights.tableCaption")}</caption>
          <thead className="bg-sunken/60 text-left text-xs text-muted">
            <tr>
              <th className="px-4 py-2.5 font-semibold">{t("insights.month")}</th>
              <th className="px-3 py-2.5 text-right font-semibold">{t("insights.paidCol")}</th>
              <th className="px-3 py-2.5 text-right font-semibold">{t("insights.couponCol")}</th>
              <th className="px-3 py-2.5 text-right font-semibold">{t("insights.freeCol")}</th>
              <th className="px-3 py-2.5 text-right font-semibold">{t("insights.gross")}</th>
              <th className="px-3 py-2.5 text-right font-semibold">{t("insights.refunds")}</th>
              <th className="px-4 py-2.5 text-right font-semibold">{t("insights.net")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border tabular-nums">
            {[...d.months].reverse().map((m) => (
              <tr key={m.month}>
                <td className="px-4 py-2.5 font-medium">{formatMonth(m.month)}</td>
                <td className="px-3 py-2.5 text-right">{m.enrol_paid}</td>
                <td className="px-3 py-2.5 text-right">{m.enrol_coupon}</td>
                <td className="px-3 py-2.5 text-right">{m.enrol_free}</td>
                <td className="px-3 py-2.5 text-right">{money(m.gross_cents)}</td>
                <td className="px-3 py-2.5 text-right">{m.refunds_cents ? money(m.refunds_cents) : "—"}</td>
                <td className="px-4 py-2.5 text-right font-semibold">{money(m.net_cents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card className="flex flex-col gap-3">
        <CardTitle>{t("insights.topCoupons")}</CardTitle>
        {d.top_coupons.length === 0 ? (
          <p className="text-sm text-muted">{t("insights.noCoupons")}</p>
        ) : (
          <ul className="divide-y divide-border">
            {d.top_coupons.map((k) => (
              <li key={k.code} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
                <span className="rounded-ez border border-dashed border-brand/40 bg-brand-50 px-2 py-0.5 font-mono font-bold tracking-wider text-brand">{k.code}</span>
                <span className="text-muted tabular-nums">
                  {t("insights.couponUses", { count: k.uses })} · {t("insights.couponGiven", { amount: money(k.discount_cents) })} · {money(k.revenue_cents)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <p className="text-xs text-muted">{t("insights.note")}</p>
    </div>
  );
}
