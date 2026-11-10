import { CheckCircle2, RotateCcw } from "lucide-react";
import Link from "next/link";

import type { Schema } from "@eduzone/api-client";
import { Badge, EmptyState, ErrorText, FilterChips, PageHeader, buttonClass } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatDateTime, formatMoney } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";

type RefundPage = Schema<"PlatformRefundPage">;

const FILTERS = ["open", "processed", "rejected", "all"] as const;
type Filter = (typeof FILTERS)[number];

const refundTone = { requested: "warning", approved: "info", processed: "success", rejected: "neutral" } as const;

/** Course refunds the automatic rule didn't settle: waiting for a decision, or for the gateway. */
export default async function RefundsPage({ searchParams }: PageProps<"/refunds">) {
  const sp = await searchParams;
  const filter: Filter = FILTERS.includes(sp.filter as Filter) ? (sp.filter as Filter) : "open";
  const cursor = typeof sp.cursor === "string" ? sp.cursor : null;
  const q = new URLSearchParams({ status: filter, limit: "50", ...(cursor ? { cursor } : {}) });
  const [res, open] = await Promise.all([
    api<RefundPage>(`/platform/refunds?${q}`),
    api<RefundPage>("/platform/refunds?status=open&limit=100"),
  ]);
  const openCount = open.ok ? open.data.items.length : undefined;

  return (
    <>
      <PageHeader title={t("platform.nav.refunds")} description={t("platform.refunds.body")} />
      <FilterChips items={FILTERS.map((f) => ({
        href: f === "open" ? "/refunds" : `/refunds?filter=${f}`,
        label: t(`platform.refunds.filter.${f}`),
        active: f === filter,
        count: f === "open" && openCount ? openCount : undefined,
      }))} />
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.items.length === 0 && (
        filter === "open"
          ? <EmptyState icon={<CheckCircle2 />} title={t("platform.refunds.emptyOpen")} body={t("platform.refunds.emptyOpenBody")} />
          : <EmptyState icon={<RotateCcw />} title={t("platform.refunds.empty")} />
      )}
      {res.ok && res.data.items.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-ez-lg border border-border bg-surface">
          {res.data.items.map((r) => (
            <li key={r.id}>
              <Link href={`/refunds/${r.id}`} className="flex flex-col gap-1 p-4 hover:bg-sunken/50 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2 font-medium">
                    <span className="truncate">{r.course_title}</span>
                    {r.status === "approved" && r.failure_reason && <Badge tone="danger">{t("platform.refunds.needsGateway")}</Badge>}
                    {r.auto_approved && <Badge tone="neutral">{t("platform.refunds.auto")}</Badge>}
                  </p>
                  <p className="truncate text-sm text-muted">
                    {r.student_name} · {r.tenant_name} · {formatDateTime(r.created_at)}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-medium tabular-nums">{formatMoney(r.amount_cents, r.currency)}</span>
                  <Badge tone={refundTone[r.status as keyof typeof refundTone] ?? "neutral"}>
                    {t(`platform.refunds.status.${r.status as keyof typeof refundTone}`)}
                  </Badge>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {res.ok && res.data.next_cursor && (
        <Link href={`/refunds?${new URLSearchParams({ ...(filter !== "open" ? { filter } : {}), cursor: res.data.next_cursor })}`}
              className={`${buttonClass.link} self-end`}>
          {t("classes.loadMore")}
        </Link>
      )}
    </>
  );
}
