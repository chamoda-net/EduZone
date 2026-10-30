import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { getMe } from "@/lib/session";
import { formatDateTime, formatMoney } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import { orderTone } from "@eduzone/lib/orders";
import type { Order } from "@eduzone/lib/types";
import { Badge, DataList, ErrorText, LogoMark } from "@eduzone/ui";

import { PrintButton } from "./print-button";

/** Printable receipt for one order. */
export default async function ReceiptPage({ params }: PageProps<"/learn/payments/[id]">) {
  const { id } = await params;
  if (!(await getMe())) redirect(`/login?next=/learn/payments/${id}`);
  const res = await api<Order>(`/learn/orders/${id}`);
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    return <SiteShell width="sm"><ErrorText>{errorText(t, res.error)}</ErrorText></SiteShell>;
  }
  const o = res.data;
  const method = [o.method?.toUpperCase(), o.card_last4 && t("receipt.card", { last4: o.card_last4 })].filter(Boolean).join(", ");

  return (
    <SiteShell width="sm">
      <Link href="/learn/payments" className="ez-no-print inline-flex items-center gap-1.5 self-start text-sm font-semibold text-muted hover:text-foreground">
        <ArrowLeft className="size-4" />
        {t("receipt.back")}
      </Link>

      <article className="ez-rise relative overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-lg print:border-0 print:shadow-none">
        <div className="ez-grain flex items-start justify-between gap-4 bg-brand-900 px-6 py-6 text-on-brand">
          <div className="flex items-center gap-3">
            <LogoMark />
            <div>
              <p className="font-semibold">{o.org?.name}</p>
              <p className="text-xs text-brand-100/70">{t("receipt.title")}</p>
            </div>
          </div>
          <Badge tone={orderTone[o.status]} dot>
            {t(`payments.status.${o.status}`)}
          </Badge>
        </div>

        <div className="flex flex-col gap-1 border-b border-dashed border-border-strong px-6 py-6 text-center">
          <p className="text-xs font-semibold tracking-[0.14em] text-muted uppercase">{t("receipt.amount")}</p>
          <p className="font-display text-4xl font-semibold tabular-nums">{formatMoney(o.total_cents, o.currency)}</p>
          <p className="text-sm text-muted">{o.item.description}</p>
        </div>

        <div className="px-6 py-2">
          <DataList
            items={[
              [t("receipt.orderNo"), <span key="n" className="font-mono text-[0.85rem]">{o.order_no}</span>],
              [t("receipt.date"), formatDateTime(o.paid_at ?? o.created_at)],
              [t("receipt.item"), o.item.description],
              ...(method ? [[t("receipt.method"), method] as [string, string]] : []),
            ]}
          />
        </div>
        <p className="border-t border-border bg-sunken/50 px-6 py-4 text-xs leading-relaxed text-muted">
          {t("receipt.issuedBy", { org: o.org?.name ?? "" })}
        </p>
      </article>

      <div className="self-start">
        <PrintButton />
      </div>
    </SiteShell>
  );
}
