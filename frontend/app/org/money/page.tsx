import Link from "next/link";

import { Card, ErrorText } from "@/components/ui";
import { api } from "@/lib/api";
import { colomboMonth, formatMoney, formatMonth, shiftMonth } from "@/lib/format";
import { errorText, t, type MessageKey } from "@/lib/i18n";
import type { Cashflow, CashflowFigures } from "@/lib/types";

type Preset = "12" | "3" | "year";

function range(preset: Preset): { from: string; to: string } {
  const to = colomboMonth();
  if (preset === "year") return { from: `${to.slice(0, 4)}-01`, to };
  return { from: shiftMonth(to, preset === "3" ? -2 : -11), to };
}

/** Monthly cash flow from the ledger. Owners and admins only (the API enforces it). */
export default async function MoneyPage({ searchParams }: PageProps<"/org/money">) {
  const sp = await searchParams;
  const preset: Preset = sp.range === "3" || sp.range === "year" ? sp.range : "12";
  const { from, to } = range(preset);
  const res = await api<Cashflow>(`/org/cashflow?from=${from}&to=${to}`);

  if (!res.ok) {
    return (
      <>
        <h1 className="text-2xl font-semibold">{t("money.title")}</h1>
        <ErrorText>{res.status === 403 ? t("money.ownersOnly") : errorText(t, res.error)}</ErrorText>
      </>
    );
  }
  const c = res.data;
  const money = (cents: number) => formatMoney(cents, c.currency);
  const columns: [keyof CashflowFigures, MessageKey][] = [
    ["gross_sales_cents", "money.gross"],
    ["refunds_cents", "money.refunds"],
    ["gateway_fees_cents", c.gateway_fee_bearer === "platform" ? "money.feesPlatform" : "money.fees"],
    ["commission_cents", "money.commission"],
    ["net_cents", "money.net"],
    ["paid_out_cents", "money.paidOut"],
  ];
  const months = [...c.months].reverse(); // newest first

  return (
    <>
      <div>
        <h1 className="text-2xl font-semibold">{t("money.title")}</h1>
        <p className="text-sm text-muted">{t("money.subtitle")}</p>
      </div>

      <Card className="flex flex-col gap-1">
        <p className="text-sm text-muted">{t("money.balanceDue")}</p>
        <p className="text-3xl font-semibold">{money(c.balance_due_cents)}</p>
        <p className="text-xs text-muted">{t("money.balanceHint")}</p>
        <p className="text-xs text-muted">
          {t("money.rate", { rate: c.commission_bps / 100, bearer: t(`money.bearer.${c.gateway_fee_bearer}`) })}
        </p>
      </Card>

      <div className="flex gap-2 overflow-x-auto">
        {(["12", "3", "year"] as const).map((p) => (
          <Link
            key={p}
            href={p === "12" ? "/org/money" : `/org/money?range=${p}`}
            className={`rounded-full border px-3 py-1.5 text-sm whitespace-nowrap ${
              p === preset ? "border-brand bg-brand text-white" : "border-border bg-surface"
            }`}
          >
            {t(`money.range.${p}`)}
          </Link>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {columns.map(([field, label]) => (
          <Card key={field} className="flex flex-col gap-1 p-3 sm:p-4">
            <p className="text-xs text-muted">{t(label)}</p>
            <p className={`text-lg font-semibold ${field === "net_cents" ? "text-brand" : ""}`}>{money(c.totals[field])}</p>
          </Card>
        ))}
      </div>

      {/* Phones: one card per month. Wider screens: a table. */}
      <ul className="flex flex-col gap-2 sm:hidden">
        {months.map((m) => (
          <li key={m.month}>
            <Card className="flex flex-col gap-1 p-3">
              <p className="font-medium">{formatMonth(m.month)}</p>
              {columns.map(([field, label]) => (
                <div key={field} className="flex justify-between text-sm">
                  <span className="text-muted">{t(label)}</span>
                  <span>{money(m[field])}</span>
                </div>
              ))}
            </Card>
          </li>
        ))}
      </ul>
      <div className="hidden overflow-x-auto rounded-xl border border-border bg-surface sm:block">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-muted">
            <tr className="border-b border-border">
              <th className="p-3 font-medium">{t("money.month")}</th>
              {columns.map(([field, label]) => (
                <th key={field} className="p-3 text-right font-medium">{t(label)}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {months.map((m) => (
              <tr key={m.month}>
                <td className="p-3 whitespace-nowrap">{formatMonth(m.month)}</td>
                {columns.map(([field]) => (
                  <td key={field} className={`p-3 text-right tabular-nums ${field === "net_cents" ? "font-medium" : ""}`}>
                    {money(m[field])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
          <tfoot className="border-t border-border font-medium">
            <tr>
              <td className="p-3">{t("money.totals")}</td>
              {columns.map(([field]) => (
                <td key={field} className="p-3 text-right tabular-nums">{money(c.totals[field])}</td>
              ))}
            </tr>
          </tfoot>
        </table>
      </div>
    </>
  );
}
