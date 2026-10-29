import Link from "next/link";
import { notFound } from "next/navigation";

import { Badge, Card, ErrorText, buttonClass } from "@eduzone/ui";
import { api } from "@/lib/api";
import { centsToRupeesInput, formatDateTime, formatMoney } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import { tenantTone } from "@/lib/platform";
import type { Payout, PlatformTenant } from "@eduzone/lib/types";

import { recordPayout, updateTenant } from "../../../actions";
import { TenantForm } from "../../tenant-form";
import { PayoutForm } from "./payout-form";

export default async function TenantPage({ params }: PageProps<"/tenants/[id]">) {
  const { id } = await params;
  const [res, payouts] = await Promise.all([
    api<PlatformTenant>(`/platform/tenants/${id}`),
    api<Payout[]>(`/platform/tenants/${id}/payouts`),
  ]);
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    return <ErrorText>{errorText(t, res.error)}</ErrorText>;
  }
  const x = res.data;
  const money = (c: number) => formatMoney(c, x.currency);

  return (
    <>
      <Link href="/" className={`${buttonClass.link} text-sm`}>← {t("platform.back")}</Link>
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold">
          {x.name} <Badge tone={tenantTone[x.status]}>{t(`platform.status.${x.status}`)}</Badge>
        </h1>
        <p className="text-sm text-muted">{x.slug} · {t(`platform.orgType.${x.org_type}`)}</p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          [t("platform.tenants.balance"), money(x.balance_due_cents)],
          [t("platform.tenants.salesMonth"), money(x.sales_this_month_cents)],
          [t("platform.tenants.students"), String(x.students)],
          [t("platform.form.commission"), `${x.commission_bps / 100}%`],
        ].map(([label, value]) => (
          <Card key={label} className="flex flex-col gap-1 p-3 sm:p-4">
            <p className="text-xs text-muted">{label}</p>
            <p className="text-lg font-semibold">{value}</p>
          </Card>
        ))}
      </div>

      <Card className="flex flex-col gap-3">
        <div>
          <h2 className="text-lg font-semibold">{t("platform.payout.title")}</h2>
          <p className="text-sm text-muted">{t("platform.payout.body")}</p>
          {x.payout_bank_name && (
            <p className="text-sm">{x.payout_bank_name} {x.payout_account_masked}</p>
          )}
        </div>
        <PayoutForm action={recordPayout.bind(null, x.id)} maxRupees={centsToRupeesInput(x.balance_due_cents)} />
        <h3 className="pt-2 text-sm font-semibold text-muted">{t("platform.payout.history")}</h3>
        {payouts.ok && payouts.data.length === 0 && <p className="text-sm text-muted">{t("platform.payout.none")}</p>}
        {payouts.ok && payouts.data.length > 0 && (
          <ul className="divide-y divide-border">
            {payouts.data.map((p) => (
              <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                <span>
                  {p.period_start} → {p.period_end} · {p.bank_reference}
                  <span className="text-muted">
                    {" · "}{formatDateTime(p.sent_at ?? p.created_at)}
                    {p.created_by_name ? ` · ${t("platform.payout.by", { name: p.created_by_name })}` : ""}
                  </span>
                </span>
                <span className="font-medium">{money(p.amount_cents)}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div className="flex">
        <Link href={`/payments?tenant_id=${x.id}`} className={buttonClass.link}>{t("platform.nav.payments")} →</Link>
      </div>

      <Card>
        <TenantForm action={updateTenant.bind(null, x.id)} initial={x} />
      </Card>
    </>
  );
}
