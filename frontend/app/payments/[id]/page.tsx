import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { StudentHeader } from "@/components/student-header";
import { Badge, Card, ErrorText, buttonClass } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDateTime, formatMoney } from "@/lib/format";
import { errorText, t } from "@/lib/i18n";
import { orderTone } from "@/lib/orders";
import { getBranding, getMe } from "@/lib/session";
import type { Order } from "@/lib/types";

import { PrintButton } from "./print-button";

/** Printable receipt for one order. */
export default async function ReceiptPage({ params }: PageProps<"/payments/[id]">) {
  const { id } = await params;
  if (!(await getMe())) redirect(`/login?next=/payments/${id}`);
  const [res, branding] = await Promise.all([api<Order>(`/student/orders/${id}`), getBranding()]);
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    return <ErrorText>{errorText(t, res.error)}</ErrorText>;
  }
  const o = res.data;
  const method = [o.method?.toUpperCase(), o.card_last4 && t("receipt.card", { last4: o.card_last4 })]
    .filter(Boolean)
    .join(", ");
  const rows: [string, string][] = [
    [t("receipt.orderNo"), o.order_no],
    [t("receipt.date"), formatDateTime(o.paid_at ?? o.created_at)],
    [t("receipt.item"), o.item.description],
    [t("receipt.amount"), formatMoney(o.total_cents, o.currency)],
    ...(method ? [[t("receipt.method"), method] as [string, string]] : []),
  ];

  return (
    <>
      <div className="print:hidden">
        <StudentHeader />
      </div>
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-4 px-4 py-8">
        <Link href="/payments" className={`${buttonClass.link} text-sm print:hidden`}>← {t("receipt.back")}</Link>
        <Card className="flex flex-col gap-4 print:border-0">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-semibold">{branding?.name}</p>
              <h1 className="text-2xl font-semibold">{t("receipt.title")}</h1>
            </div>
            <Badge tone={orderTone[o.status]}>{t(`payments.status.${o.status}`)}</Badge>
          </div>
          <dl className="divide-y divide-border">
            {rows.map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 py-2 text-sm">
                <dt className="text-muted">{k}</dt>
                <dd className="text-right font-medium">{v}</dd>
              </div>
            ))}
          </dl>
          <p className="text-xs text-muted">{t("receipt.issuedBy", { org: branding?.name ?? "" })}</p>
        </Card>
        <div className="self-start">
          <PrintButton />
        </div>
      </main>
    </>
  );
}
