import Link from "next/link";
import { redirect } from "next/navigation";

import { StudentHeader } from "@/components/student-header";
import { Badge, ErrorText } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDateTime, formatMoney } from "@/lib/format";
import { errorText, t } from "@/lib/i18n";
import { getMe } from "@/lib/session";
import { orderTone } from "@/lib/orders";
import type { Order } from "@/lib/types";

export default async function PaymentsPage() {
  if (!(await getMe())) redirect("/login?next=/payments");
  const res = await api<Order[]>("/student/orders");

  return (
    <>
      <StudentHeader />
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-5 px-4 py-8">
        <h1 className="text-2xl font-semibold">{t("payments.title")}</h1>
        {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
        {res.ok && res.data.length === 0 && <p className="text-muted">{t("payments.empty")}</p>}
        {res.ok && res.data.length > 0 && (
          <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
            {res.data.map((o) => (
              <li key={o.id}>
                <Link href={`/payments/${o.id}`} className="flex flex-col gap-1 p-4 hover:bg-background sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{o.item.description}</p>
                    <p className="text-sm text-muted">{o.order_no} · {formatDateTime(o.paid_at ?? o.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-medium">{formatMoney(o.total_cents, o.currency)}</span>
                    <Badge tone={orderTone[o.status]}>{t(`payments.status.${o.status}`)}</Badge>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </>
  );
}
