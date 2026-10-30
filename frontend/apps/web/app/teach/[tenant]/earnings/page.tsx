import { teachHref } from "@/lib/workspace";
import { HandCoins } from "lucide-react";
import Link from "next/link";

import { buttonClass, Card, EmptyState, ErrorText } from "@eduzone/ui";
import { api } from "@/lib/api";
import { colomboMonth, formatMoney, formatMonth, shiftMonth } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import type { Earnings } from "@eduzone/lib/types";

/** Net per teacher for one month. Owners and admins see everyone; a teacher sees themself. */
export default async function EarningsPage({ searchParams }: PageProps<"/teach/[tenant]/earnings">) {
  const base = await teachHref();
  const sp = await searchParams;
  const month = typeof sp.month === "string" && /^\d{4}-\d{2}$/.test(sp.month) ? sp.month : colomboMonth();
  const res = await api<Earnings>(`~/earnings?month=${month}`);
  const isCurrent = month >= colomboMonth();

  return (
    <>
      <div>
        <h1 className="font-display text-3xl font-semibold sm:text-4xl">{t("earnings.title")}</h1>
        <p className="text-sm text-muted">{t("earnings.subtitle")}</p>
      </div>

      <div className="flex items-center justify-between gap-2">
        <Link href={`${base}/earnings?month=${shiftMonth(month, -1)}`} className={`${buttonClass.link} text-sm`}>
          ← {t("earnings.prev")}
        </Link>
        <span className="font-medium">{formatMonth(`${month}-01`)}</span>
        {isCurrent ? <span /> : (
          <Link href={`${base}/earnings?month=${shiftMonth(month, 1)}`} className={`${buttonClass.link} text-sm`}>
            {t("earnings.next")} →
          </Link>
        )}
      </div>

      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.teachers.length === 0 && <EmptyState icon={<HandCoins />} title={t("earnings.empty")} />}
      {res.ok && res.data.teachers.length > 0 && (() => {
        const e = res.data;
        const money = (cents: number) => formatMoney(cents, e.currency);
        return (
          <Card className="flex flex-col p-0 sm:p-0">
            <ul className="divide-y divide-border">
              {e.teachers.map((r) => (
                <li key={r.teacher_member_id} className="flex flex-col gap-1 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="font-medium">{r.teacher_name}</p>
                    <p className="text-xs text-muted">
                      {t("earnings.sales")}: {r.sales_count} · {t("money.gross")}: {money(r.gross_sales_cents)}
                      {r.refunds_cents ? ` · ${t("money.refunds")}: ${money(r.refunds_cents)}` : ""}
                      {` · ${t("money.commission")}: ${money(r.commission_cents)}`}
                    </p>
                  </div>
                  <p className="text-lg font-semibold tabular-nums">{money(r.net_cents)}</p>
                </li>
              ))}
            </ul>
            {e.teachers.length > 1 && (
              <div className="flex justify-between border-t border-border p-4 font-semibold">
                <span>{t("earnings.total")}</span>
                <span className="tabular-nums">{money(e.total_net_cents)}</span>
              </div>
            )}
          </Card>
        );
      })()}
    </>
  );
}
