import { Receipt } from "lucide-react";
import Link from "next/link";

import { Badge, buttonClass, EmptyState, ErrorText } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatDateTime, formatMoney } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import { orderTone } from "@eduzone/lib/orders";
import type { OrderStatus, OrgOrderPage } from "@eduzone/lib/types";

const FILTERS: (OrderStatus | null)[] = [null, "paid", "pending", "failed", "cancelled"];

/** Orders for the organization's classes (a teacher sees their own classes only). */
export default async function OrgPaymentsPage({ searchParams }: PageProps<"/org/payments">) {
  const sp = await searchParams;
  const status = FILTERS.includes(sp.status as OrderStatus) ? (sp.status as OrderStatus) : null;
  const cursor = typeof sp.cursor === "string" ? sp.cursor : null;
  const q = new URLSearchParams({ limit: "30" });
  if (status) q.set("status", status);
  if (cursor) q.set("cursor", cursor);
  const res = await api<OrgOrderPage>(`/org/orders?${q}`);
  const href = (s: OrderStatus | null, c?: string) => {
    const p = new URLSearchParams();
    if (s) p.set("status", s);
    if (c) p.set("cursor", c);
    return p.size ? `/org/payments?${p}` : "/org/payments";
  };

  return (
    <>
      <h1 className="font-display text-3xl font-semibold sm:text-4xl">{t("orgPayments.title")}</h1>
      <div className="flex gap-2 overflow-x-auto">
        {FILTERS.map((f) => (
          <Link
            key={f ?? "all"}
            href={href(f)}
            className={`inline-flex min-h-10 shrink-0 items-center rounded-full border px-4 text-sm font-semibold whitespace-nowrap transition-all ${
              f === status ? "border-brand-800 bg-brand-800 text-on-brand shadow-ez-sm" : "border-border-strong bg-surface text-muted hover:border-foreground/40 hover:text-foreground"
            }`}
          >
            {f ? t(`payments.status.${f}`) : t("classes.filter.all")}
          </Link>
        ))}
      </div>
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.items.length === 0 && <EmptyState icon={<Receipt />} title={t("orgPayments.empty")} />}
      {res.ok && res.data.items.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-ez-lg border border-border bg-surface">
          {res.data.items.map((o) => (
            <li key={o.id} className="flex flex-col gap-1 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="truncate font-medium">{o.item.description}</p>
                <p className="text-sm text-muted">
                  {o.student_name} · {o.student_phone} · {o.order_no} · {formatDateTime(o.paid_at ?? o.created_at)}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-medium">{formatMoney(o.total_cents, o.currency)}</span>
                <Badge tone={orderTone[o.status]}>{t(`payments.status.${o.status}`)}</Badge>
              </div>
            </li>
          ))}
        </ul>
      )}
      {res.ok && res.data.next_cursor && (
        <Link href={href(status, res.data.next_cursor)} className={`${buttonClass.link} self-end`}>
          {t("classes.loadMore")}
        </Link>
      )}
    </>
  );
}
