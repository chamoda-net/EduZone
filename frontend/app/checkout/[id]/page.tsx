import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { StudentHeader } from "@/components/student-header";
import { Card, ErrorText, buttonClass } from "@/components/ui";
import { api } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { errorText, t } from "@/lib/i18n";
import { getMe } from "@/lib/session";
import type { Order } from "@/lib/types";

import { OrderPoller } from "./poller";

/** Where the gateway sends the browser back. Shows the order's real status (set only by the
 * gateway's server-to-server notification) and waits while it's still pending. */
export default async function CheckoutReturnPage({ params }: PageProps<"/checkout/[id]">) {
  const { id } = await params;
  if (!(await getMe())) redirect(`/login?next=/checkout/${id}`);
  const res = await api<Order>(`/student/orders/${id}`);
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    return <ErrorText>{errorText(t, res.error)}</ErrorText>;
  }
  const o = res.data;
  const classUrl = `/classes/${o.item.class_slug}`;

  return (
    <>
      <StudentHeader />
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-4 px-4 py-10">
        <Card className="flex flex-col items-start gap-3">
          <p className="text-sm text-muted">
            {o.item.description} · {formatMoney(o.total_cents, o.currency)}
          </p>
          {o.status === "pending" && (
            <>
              <h1 className="flex items-center gap-2 text-xl font-semibold">
                <span aria-hidden className="h-4 w-4 animate-spin rounded-full border-2 border-brand border-t-transparent" />
                {t("checkout.confirming")}
              </h1>
              <p className="text-muted">{t("checkout.confirmingBody")}</p>
              <OrderPoller orderId={o.id} />
            </>
          )}
          {o.status === "paid" && (
            <>
              <h1 className="text-xl font-semibold text-green-700 dark:text-green-400">✓ {t("checkout.paid")}</h1>
              <p>{t("checkout.paidBody", { item: o.item.description })}</p>
              <div className="flex flex-wrap gap-2">
                <Link href={classUrl} className={buttonClass.primary}>{t("checkout.toClass")}</Link>
                <Link href={`/payments/${o.id}`} className={buttonClass.secondary}>{t("checkout.receipt")}</Link>
              </div>
            </>
          )}
          {(o.status === "failed" || o.status === "cancelled") && (
            <>
              <h1 className="text-xl font-semibold">
                {o.status === "cancelled" ? t("checkout.cancelled") : t("checkout.failed")}
              </h1>
              <p className="text-muted">{t("checkout.failedBody")}</p>
              <Link href={classUrl} className={buttonClass.primary}>{t("checkout.tryAgain")}</Link>
            </>
          )}
        </Card>
      </main>
    </>
  );
}
