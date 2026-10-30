import { ArrowRight, Check, Receipt, RotateCcw, X } from "lucide-react";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { getMe } from "@/lib/session";
import { formatMoney } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import type { Order } from "@eduzone/lib/types";
import { ErrorText, Spinner, buttonStyles, cx } from "@eduzone/ui";

import { OrderPoller } from "./poller";

/** Where the gateway sends the browser back. Shows the order's real status (set only by the
 * gateway's server-to-server notification) and waits while it's still pending. */
export default async function CheckoutReturnPage({ params }: PageProps<"/checkout/[id]">) {
  const { id } = await params;
  if (!(await getMe())) redirect(`/login?next=/checkout/${id}`);
  const res = await api<Order>(`/learn/orders/${id}`);
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    return <SiteShell width="sm"><ErrorText>{errorText(t, res.error)}</ErrorText></SiteShell>;
  }
  const o = res.data;
  const classUrl = `/learn/classes/${o.item.class_id}`;
  const failed = o.status === "failed" || o.status === "cancelled";

  return (
    <SiteShell width="sm">
      <div className="ez-rise flex flex-col items-center gap-6 rounded-ez-lg border border-border bg-surface px-6 py-10 text-center shadow-ez-lg sm:px-10">
        <div
          className={cx(
            "grid size-20 place-items-center rounded-full ring-8",
            o.status === "paid" && "bg-success text-on-brand ring-success-bg",
            o.status === "pending" && "bg-brand-50 text-brand ring-brand-50/50",
            failed && "bg-danger-bg text-danger ring-danger-bg/50",
          )}
        >
          {o.status === "paid" && <Check className="size-9" strokeWidth={2.5} />}
          {o.status === "pending" && <Spinner className="size-8" />}
          {failed && <X className="size-9" strokeWidth={2.5} />}
        </div>

        {o.status === "pending" && (
          <div className="flex flex-col gap-2">
            <h1 className="font-display text-3xl font-semibold">{t("checkout.confirming")}</h1>
            <p className="text-muted">{t("checkout.confirmingBody")}</p>
            <OrderPoller orderId={o.id} />
          </div>
        )}
        {o.status === "paid" && (
          <div className="flex flex-col gap-2">
            <h1 className="font-display text-3xl font-semibold">{t("checkout.paid")}</h1>
            <p className="text-muted">{t("checkout.paidBody", { item: o.item.description })}</p>
          </div>
        )}
        {failed && (
          <div className="flex flex-col gap-2">
            <h1 className="font-display text-3xl font-semibold">
              {o.status === "cancelled" ? t("checkout.cancelled") : t("checkout.failed")}
            </h1>
            <p className="text-muted">{t("checkout.failedBody")}</p>
          </div>
        )}

        <div className="w-full rounded-ez bg-sunken/70 px-4 py-3 text-left">
          <p className="text-xs font-semibold tracking-wide text-muted uppercase">{t("checkout.item")}</p>
          <div className="mt-1 flex items-baseline justify-between gap-3">
            <p className="font-semibold">{o.item.description}</p>
            <p className="font-display text-lg font-semibold tabular-nums">{formatMoney(o.total_cents, o.currency)}</p>
          </div>
        </div>

        {o.status === "paid" && (
          <div className="flex w-full flex-col gap-2 sm:flex-row">
            <Link href={classUrl} className={buttonStyles("primary", "lg", "flex-1")}>
              {t("checkout.toClass")}
              <ArrowRight className="size-4.5" />
            </Link>
            <Link href={`/learn/payments/${o.id}`} className={buttonStyles("secondary", "lg", "flex-1")}>
              <Receipt className="size-4.5" />
              {t("checkout.receipt")}
            </Link>
          </div>
        )}
        {failed && (
          <Link href={classUrl} className={buttonStyles("primary", "lg", "w-full")}>
            <RotateCcw className="size-4.5" />
            {t("checkout.tryAgain")}
          </Link>
        )}
      </div>
    </SiteShell>
  );
}
