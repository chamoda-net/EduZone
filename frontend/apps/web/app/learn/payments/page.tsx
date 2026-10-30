import { ChevronRight, Receipt } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { getMe } from "@/lib/session";
import { formatDateTime, formatMoney } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import { orderTone } from "@eduzone/lib/orders";
import type { Order } from "@eduzone/lib/types";
import { Badge, EmptyState, ErrorText, PageHeader, buttonStyles } from "@eduzone/ui";

export default async function PaymentsPage() {
  if (!(await getMe())) redirect("/login?next=/learn/payments");
  const res = await api<Order[]>("/learn/payments");

  return (
    <SiteShell width="md">
      <PageHeader eyebrow={t("payments.eyebrow")} title={t("payments.title")} description={t("payments.subtitle")} />
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.length === 0 && (
        <EmptyState
          icon={<Receipt />}
          title={t("payments.empty")}
          body={t("payments.emptyBody")}
          action={<Link href="/learn/classes" className={buttonStyles("primary")}>{t("nav.myClasses")}</Link>}
        />
      )}
      {res.ok && res.data.length > 0 && (
        <ul className="overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-sm">
          {res.data.map((o, i) => (
            <li key={o.id} className="ez-rise border-b border-border last:border-0" style={{ "--i": i } as React.CSSProperties}>
              <Link href={`/learn/payments/${o.id}`} className="group flex items-center gap-4 p-4 transition-colors hover:bg-sunken/50 sm:p-5">
                <span className="grid size-11 shrink-0 place-items-center rounded-ez bg-brand-50 text-brand">
                  <Receipt className="size-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold">{o.item.description}</p>
                  <p className="text-sm text-muted">
                    {[o.org?.name, o.order_no, formatDateTime(o.paid_at ?? o.created_at)].filter(Boolean).join(" · ")}
                  </p>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <span className="font-display text-lg font-semibold tabular-nums">{formatMoney(o.total_cents, o.currency)}</span>
                  <Badge tone={orderTone[o.status]} dot>{t(`payments.status.${o.status}`)}</Badge>
                </div>
                <ChevronRight className="hidden size-5 text-subtle transition-transform group-hover:translate-x-0.5 sm:block" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </SiteShell>
  );
}
