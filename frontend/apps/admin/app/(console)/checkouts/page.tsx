import { CheckCircle2, ShoppingCart } from "lucide-react";
import Link from "next/link";

import type { Schema } from "@eduzone/api-client";
import { Badge, EmptyState, ErrorText, FilterChips, PageHeader, buttonClass } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatDateTime, formatMoney } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import { orderTone } from "@eduzone/lib/orders";

type CheckoutPage = Schema<"PlatformCheckoutPage">;

const FILTERS = ["stuck", "pending", "paid", "failed", "all"] as const;
type Filter = (typeof FILTERS)[number];

/** Cart payments across organizations. "Needs a retry" first, since it is the only one asking for action. */
export default async function CheckoutsPage({ searchParams }: PageProps<"/checkouts">) {
  const sp = await searchParams;
  const filter: Filter = FILTERS.includes(sp.filter as Filter) ? (sp.filter as Filter) : "all";
  const cursor = typeof sp.cursor === "string" ? sp.cursor : null;
  const q = new URLSearchParams({ limit: "50" });
  if (filter === "stuck") q.set("stuck", "true");
  else if (filter !== "all") q.set("status", filter);
  if (cursor) q.set("cursor", cursor);
  const [res, stuck] = await Promise.all([
    api<CheckoutPage>(`/platform/checkouts?${q}`),
    api<CheckoutPage>("/platform/checkouts?stuck=true&limit=100"),
  ]);
  const stuckCount = stuck.ok ? stuck.data.items.length : undefined;
  const label = (f: Filter) =>
    f === "stuck" ? t("platform.checkouts.filter.stuck") : f === "all" ? t("platform.checkouts.filter.all") : t(`payments.status.${f}`);

  return (
    <>
      <PageHeader title={t("platform.nav.checkouts")} description={t("platform.checkouts.body")} />
      <FilterChips items={FILTERS.map((f) => ({
        href: f === "all" ? "/checkouts" : `/checkouts?filter=${f}`,
        label: label(f),
        active: f === filter,
        count: f === "stuck" && stuckCount ? stuckCount : undefined,
      }))} />
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.items.length === 0 && (
        filter === "stuck"
          ? <EmptyState icon={<CheckCircle2 />} title={t("platform.checkouts.emptyStuck")} />
          : <EmptyState icon={<ShoppingCart />} title={t("platform.checkouts.empty")} />
      )}
      {res.ok && res.data.items.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-ez-lg border border-border bg-surface">
          {res.data.items.map((c) => (
            <li key={c.id}>
              <Link href={`/checkouts/${c.id}`} className="flex flex-col gap-1 p-4 hover:bg-sunken/50 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2 font-medium">
                    <span className="font-mono text-sm">{c.checkout_no}</span>
                    {c.stuck && <Badge tone="danger">{t("platform.checkouts.stuck")}</Badge>}
                  </p>
                  <p className="truncate text-sm text-muted">
                    {c.student_name} · {t("platform.checkouts.orders", { paid: c.orders_paid, count: c.orders })} ·{" "}
                    {formatDateTime(c.paid_at ?? c.created_at)}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-medium tabular-nums">{formatMoney(c.total_cents, c.currency)}</span>
                  <Badge tone={orderTone[c.status as keyof typeof orderTone]}>{t(`payments.status.${c.status as "paid"}`)}</Badge>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {res.ok && res.data.next_cursor && (
        <Link href={`/checkouts?${new URLSearchParams({ ...(filter !== "all" ? { filter } : {}), cursor: res.data.next_cursor })}`}
              className={`${buttonClass.link} self-end`}>
          {t("classes.loadMore")}
        </Link>
      )}
    </>
  );
}
