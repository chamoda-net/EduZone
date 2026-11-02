import { AlertTriangle } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import type { Schema } from "@eduzone/api-client";
import { ActionButton } from "@eduzone/ui/action-button";
import { Badge, Card, CardTitle, DataList, ErrorText, buttonClass } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatDateTime, formatMoney } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import { orderTone } from "@eduzone/lib/orders";

import { retryCheckout } from "../../../actions";

type Detail = Schema<"PlatformCheckoutDetail">;

const attemptTone = { initiated: "neutral", succeeded: "success", failed: "danger", cancelled: "neutral" } as const;

/** One cart payment: the student, its orders (one per organization) and the gateway attempts. */
export default async function CheckoutPage({ params }: PageProps<"/checkouts/[id]">) {
  const { id } = await params;
  const res = await api<Detail>(`/platform/checkouts/${id}`);
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    return <ErrorText>{errorText(t, res.error)}</ErrorText>;
  }
  const c = res.data;
  const money = (cents: number) => formatMoney(cents, c.currency);
  const status = (s: string) => t(`payments.status.${s as "paid"}`);

  return (
    <>
      <Link href="/checkouts" className={`${buttonClass.link} text-sm`}>← {t("platform.checkouts.back")}</Link>
      <header className="flex flex-col gap-1">
        <h1 className="flex flex-wrap items-center gap-3 font-display text-3xl font-semibold">
          <span className="font-mono text-2xl">{c.checkout_no}</span>
          <Badge tone={orderTone[c.status as keyof typeof orderTone]}>{status(c.status)}</Badge>
        </h1>
        <p className="text-sm text-muted">
          {t("platform.checkouts.started", { date: formatDateTime(c.created_at) })}
          {c.paid_at && ` · ${t("platform.checkouts.paidOn", { date: formatDateTime(c.paid_at) })}`}
        </p>
      </header>

      {c.stuck && (
        <div role="status" className="flex flex-col gap-3 rounded-ez-lg border border-danger/25 bg-danger-bg p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex gap-3">
            <AlertTriangle className="mt-0.5 size-5 shrink-0 text-danger" aria-hidden />
            <div>
              <p className="font-semibold text-danger">{t("platform.checkouts.stuckTitle")}</p>
              <p className="text-sm text-foreground/80">{t("platform.checkouts.stuckBody")}</p>
            </div>
          </div>
          <ActionButton variant="danger" action={retryCheckout.bind(null, c.id)} label={t("platform.checkouts.retry")}
                        done={t("platform.checkouts.retried")} />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_2fr]">
        <Card>
          <DataList items={[
            [t("orgPayments.student"), <Link key="s" href={`/users/${c.user_id}`} className="text-brand hover:underline">{c.student_name}</Link>],
            [t("auth.phone"), c.student_phone ?? "—"],
            [t("auth.email"), c.student_email ?? "—"],
            [t("cart.total"), <span key="t" className="tabular-nums">{money(c.total_cents)}</span>],
          ]} />
        </Card>

        <Card className="flex flex-col gap-3">
          <CardTitle>{t("platform.checkouts.orderList")}</CardTitle>
          <ul className="divide-y divide-border">
            {c.order_list.map((o) => (
              <li key={o.order_id} className="flex flex-col gap-1 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="truncate font-medium">{o.description}</p>
                  <p className="text-sm text-muted">
                    <Link href={`/tenants/${o.tenant_id}`} className="text-brand hover:underline">{o.tenant_name}</Link>
                    {` · ${o.order_no}`}
                    {o.gateway_fee_cents !== null && ` · ${t("platform.checkouts.fee", { amount: money(o.gateway_fee_cents) })}`}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-medium tabular-nums">{money(o.total_cents)}</span>
                  <Badge tone={orderTone[o.status as keyof typeof orderTone]}>{status(o.status)}</Badge>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card className="flex flex-col gap-3">
        <CardTitle>{t("platform.checkouts.attempts")}</CardTitle>
        <ul className="divide-y divide-border">
          {c.attempts.map((a) => (
            <li key={a.id} className="flex flex-col gap-1 py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="font-medium">
                  {a.gateway}
                  {a.gateway_payment_ref && <span className="font-mono text-muted"> {a.gateway_payment_ref}</span>}
                  {a.card_last4 && <span className="text-muted"> · {t("receipt.card", { last4: a.card_last4 })}</span>}
                </p>
                <p className="truncate text-xs text-muted">
                  <span className="font-mono">{a.idempotency_key}</span> · {formatDateTime(a.created_at)}
                  {a.gateway_fee_cents !== null && ` · ${t("platform.checkouts.fee", { amount: money(a.gateway_fee_cents) })}`}
                  {a.failure_reason && <span className="text-danger"> · {a.failure_reason}</span>}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="tabular-nums">{money(a.amount_cents)}</span>
                <Badge tone={attemptTone[a.status as keyof typeof attemptTone] ?? "neutral"}>
                  {t(`platform.checkouts.attempt.${a.status as keyof typeof attemptTone}`)}
                </Badge>
              </div>
            </li>
          ))}
        </ul>
      </Card>

      <Link href={`/audit?entity_id=${c.id}`} className={`${buttonClass.link} self-start text-sm`}>{t("platform.nav.audit")} →</Link>
    </>
  );
}
