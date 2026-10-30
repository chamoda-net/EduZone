import { Receipt } from "lucide-react";
import Link from "next/link";

import { Badge, buttonClass, EmptyState, ErrorText } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatDateTime, formatMoney } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import { orderTone } from "@eduzone/lib/orders";
import type { PlatformPaymentPage } from "@eduzone/lib/types";

/** Every order across all organizations, newest first. */
export default async function PlatformPaymentsPage({ searchParams }: PageProps<"/payments">) {
  const sp = await searchParams;
  const tenantId = typeof sp.tenant_id === "string" ? sp.tenant_id : null;
  const cursor = typeof sp.cursor === "string" ? sp.cursor : null;
  const q = new URLSearchParams({ limit: "50" });
  if (tenantId) q.set("tenant_id", tenantId);
  if (cursor) q.set("cursor", cursor);
  const res = await api<PlatformPaymentPage>(`/platform/payments?${q}`);

  return (
    <>
      <div className="flex items-center justify-between gap-3">
        <h1 className="font-display text-3xl font-semibold sm:text-4xl">{t("platform.nav.payments")}</h1>
        {tenantId && <Link href="/payments" className={`${buttonClass.link} text-sm`}>{t("platform.payments.all")}</Link>}
      </div>
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.items.length === 0 && <EmptyState icon={<Receipt />} title={t("orgPayments.empty")} />}
      {res.ok && res.data.items.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-ez-lg border border-border bg-surface">
          {res.data.items.map((p) => (
            <li key={p.order_id} className="flex flex-col gap-1 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="truncate font-medium">{p.description}</p>
                <p className="text-sm text-muted">
                  <Link href={`/tenants/${p.tenant_id}`} className="text-brand hover:underline">{p.tenant_name}</Link>
                  {` · ${p.student_name} · ${p.order_no} · ${formatDateTime(p.paid_at ?? p.created_at)}`}
                  {p.gateway ? ` · ${p.gateway}${p.gateway_payment_ref ? ` ${p.gateway_payment_ref}` : ""}` : ""}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-medium">{formatMoney(p.total_cents, p.currency)}</span>
                <Badge tone={orderTone[p.status]}>{t(`payments.status.${p.status}`)}</Badge>
              </div>
            </li>
          ))}
        </ul>
      )}
      {res.ok && res.data.next_cursor && (
        <Link href={`/payments?${new URLSearchParams({ ...(tenantId ? { tenant_id: tenantId } : {}), cursor: res.data.next_cursor })}`}
              className={`${buttonClass.link} self-end`}>
          {t("classes.loadMore")}
        </Link>
      )}
    </>
  );
}
