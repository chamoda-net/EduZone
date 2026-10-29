import Link from "next/link";

import { Badge, ErrorText, buttonClass } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatBytes, formatMoney } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import { tenantTone } from "@/lib/platform";
import type { PlatformTenant } from "@eduzone/lib/types";

function usage(used: number, limit: number | null): string {
  return `${formatBytes(used)} / ${limit === null ? t("platform.tenants.unlimited") : formatBytes(limit)}`;
}

/** All organizations with what EduZone owes them and their Bunny usage. */
export default async function TenantsPage() {
  const res = await api<PlatformTenant[]>("/platform/tenants");
  return (
    <>
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">{t("platform.nav.tenants")}</h1>
        <Link href="/tenants/new" className={buttonClass.primary}>{t("platform.tenants.new")}</Link>
      </div>
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.length === 0 && <p className="text-muted">{t("platform.tenants.empty")}</p>}
      {res.ok && res.data.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
          {res.data.map((x) => (
            <li key={x.id}>
              <Link href={`/tenants/${x.id}`} className="flex flex-col gap-2 p-4 hover:bg-background md:flex-row md:items-center md:justify-between">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 font-medium">
                    {x.name} <Badge tone={tenantTone[x.status]}>{t(`platform.status.${x.status}`)}</Badge>
                  </p>
                  <p className="text-sm text-muted">
                    {x.slug} · {t(`platform.orgType.${x.org_type}`)} · {t("platform.tenants.students")}: {x.students}
                  </p>
                  <p className="text-xs text-muted">
                    {t("platform.tenants.storage")}: {usage(x.storage_used_bytes, x.storage_limit_bytes)} ·{" "}
                    {t("platform.tenants.bandwidth")}:{" "}
                    {x.usage_synced_on ? usage(x.bandwidth_this_month_bytes, x.bandwidth_limit_bytes) : t("platform.tenants.notSynced")}
                  </p>
                </div>
                <div className="flex gap-6 text-sm md:text-right">
                  <div>
                    <p className="text-xs text-muted">{t("platform.tenants.salesMonth")}</p>
                    <p className="font-medium">{formatMoney(x.sales_this_month_cents, x.currency)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted">{t("platform.tenants.balance")}</p>
                    <p className="font-semibold">{formatMoney(x.balance_due_cents, x.currency)}</p>
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
