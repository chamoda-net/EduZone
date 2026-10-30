import { ArrowRight, Check, RotateCcw, ShoppingCart, X } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { getMe } from "@/lib/session";
import { formatDateTime, formatMoney } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import type { CheckoutDetail } from "@eduzone/lib/types";
import { ErrorText, Spinner, buttonStyles, cx } from "@eduzone/ui";

import { CheckoutPoller } from "./poller";
import { PrintButton } from "@/app/learn/payments/[id]/print-button";

export const metadata: Metadata = { title: "Payment | EduZone", robots: { index: false } };

/** Where the gateway sends the browser back after paying for the cart. Shows the real status (set only by the
 * gateway's server-to-server notification), waits while pending, and is the receipt once paid. */
export default async function CheckoutPage({ params }: PageProps<"/checkouts/[id]">) {
  const { id } = await params;
  if (!(await getMe())) redirect(`/login?next=/checkouts/${id}`);
  const res = await api<CheckoutDetail>(`/me/checkouts/${id}`);
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    return <SiteShell width="sm"><ErrorText>{errorText(t, res.error)}</ErrorText></SiteShell>;
  }
  const c = res.data;
  const failed = c.status === "failed" || c.status === "cancelled";
  // The gateway took the money but some orders are still being settled: keep waiting, never ask to pay again.
  const pending = c.status === "pending";

  return (
    <SiteShell width="md">
      <div className="ez-rise flex flex-col gap-6 rounded-ez-lg border border-border bg-surface px-6 py-8 shadow-ez-lg sm:px-10 print:border-0 print:shadow-none">
        <div className="flex flex-col items-center gap-4 text-center">
          <div
            className={cx(
              "ez-no-print grid size-20 place-items-center rounded-full ring-8",
              c.status === "paid" && "bg-success text-on-brand ring-success-bg",
              pending && "bg-brand-50 text-brand ring-brand-50/50",
              failed && "bg-danger-bg text-danger ring-danger-bg/50",
            )}
          >
            {c.status === "paid" && <Check className="size-9" strokeWidth={2.5} />}
            {pending && <Spinner className="size-8" />}
            {failed && <X className="size-9" strokeWidth={2.5} />}
          </div>
          <div className="flex flex-col gap-2">
            <h1 className="font-display text-3xl font-semibold">
              {c.status === "paid" ? t("checkout.paid")
                : pending ? t("checkout.confirming")
                : c.status === "cancelled" ? t("checkout.cancelled") : t("checkout.failed")}
            </h1>
            <p className="text-muted">
              {c.status === "paid" ? t("checkouts.paidBody") : pending ? t("checkout.confirmingBody") : t("checkout.failedBody")}
            </p>
            {pending && <CheckoutPoller checkoutId={c.id} />}
          </div>
        </div>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 rounded-ez bg-sunken/70 px-4 py-3 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs font-semibold tracking-wide text-muted uppercase">{t("checkouts.number")}</dt>
            <dd className="font-mono font-semibold">{c.checkout_no}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold tracking-wide text-muted uppercase">{t("cart.total")}</dt>
            <dd className="font-semibold tabular-nums">{formatMoney(c.total_cents, c.currency)}</dd>
          </div>
          <div className="col-span-2 sm:col-span-1">
            <dt className="text-xs font-semibold tracking-wide text-muted uppercase">{t("receipt.date")}</dt>
            <dd className="font-semibold">
              {formatDateTime(c.paid_at ?? c.created_at)}
              {c.card_last4 && <span className="text-muted"> · •••• {c.card_last4}</span>}
            </dd>
          </div>
        </dl>

        <section className="flex flex-col gap-3">
          <h2 className="text-xs font-bold tracking-[0.12em] text-muted uppercase">{t("checkouts.items")}</h2>
          <ul className="divide-y divide-border rounded-ez border border-border">
            {c.orders.map((o) => (
              <li key={o.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div className="min-w-0">
                  <p className="font-semibold">{o.item.description}</p>
                  <p className="text-xs text-muted">
                    {o.org && t("checkouts.paidTo", { org: o.org.name })} · {t("checkouts.order", { no: o.order_no })}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-display text-lg font-semibold tabular-nums">{formatMoney(o.total_cents, o.currency)}</span>
                  {c.status === "paid" && (
                    <Link href={`/learn/classes/${o.item.class_id}`} className={buttonStyles("secondary", "sm", "ez-no-print")}>
                      {t("checkouts.openClass")}
                      <ArrowRight className="size-4" />
                    </Link>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>

        <p className="text-xs text-muted">{t("checkouts.issuedBy")}</p>

        <div className="ez-no-print flex flex-col gap-2 sm:flex-row">
          {c.status === "paid" && (
            <>
              <Link href="/learn" className={buttonStyles("primary", "lg", "flex-1")}>
                {t("nav.myLearning")}
                <ArrowRight className="size-4.5" />
              </Link>
              <PrintButton />
            </>
          )}
          {failed && (
            <Link href="/cart" className={buttonStyles("primary", "lg", "flex-1")}>
              <RotateCcw className="size-4.5" />
              {t("checkout.tryAgain")}
            </Link>
          )}
          {pending && (
            <Link href="/cart" className={buttonStyles("ghost", "lg", "flex-1")}>
              <ShoppingCart className="size-4.5" />
              {t("checkouts.backToCart")}
            </Link>
          )}
        </div>
      </div>
    </SiteShell>
  );
}
