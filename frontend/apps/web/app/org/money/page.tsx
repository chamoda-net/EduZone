import { Landmark, Percent, TrendingUp } from "lucide-react";

import { Card, ErrorText, FilterChips, PageHeader, StatTile } from "@eduzone/ui";
import { api } from "@/lib/api";
import { colomboMonth, formatMoney, formatMonth, shiftMonth } from "@eduzone/lib/format";
import { errorText, t, type MessageKey } from "@eduzone/lib/i18n";
import type { Cashflow, CashflowFigures } from "@eduzone/lib/types";

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
        <h1 className="font-display text-3xl font-semibold sm:text-4xl">{t("money.title")}</h1>
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
      <PageHeader eyebrow={t("shell.console")} title={t("money.title")} description={t("money.subtitle")} />

      <div className="grid gap-4 md:grid-cols-[1.3fr_1fr_1fr]">
        <StatTile
          tone="brand"
          icon={<Landmark />}
          label={t("money.balanceDue")}
          value={money(c.balance_due_cents)}
          hint={t("money.balanceHint")}
        />
        <StatTile icon={<TrendingUp />} label={t("money.net")} value={money(c.totals.net_cents)} hint={t(`money.range.${preset}`)} />
        <StatTile
          tone="gold"
          icon={<Percent />}
          label={t("money.commission")}
          value={`${c.commission_bps / 100}%`}
          hint={t("money.rate", { rate: c.commission_bps / 100, bearer: t(`money.bearer.${c.gateway_fee_bearer}`) })}
        />
      </div>

      <FilterChips
        items={(["12", "3", "year"] as const).map((p) => ({
          href: p === "12" ? "/org/money" : `/org/money?range=${p}`,
          label: t(`money.range.${p}`),
          active: p === preset,
        }))}
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {columns.map(([field, label]) => (
          <Card key={field} className="flex flex-col gap-1 p-4 sm:p-5">
            <p className="text-xs font-medium text-muted">{t(label)}</p>
            <p className={`font-display text-xl font-semibold tabular-nums ${field === "net_cents" ? "text-brand" : ""}`}>
              {money(c.totals[field])}
            </p>
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
      <div className="hidden overflow-x-auto rounded-ez-lg border border-border bg-surface shadow-ez-sm sm:block">
        <table className="w-full text-sm">
          <thead className="bg-sunken/60 text-left text-xs tracking-wide text-muted uppercase">
            <tr className="border-b border-border">
              <th className="p-3 font-medium">{t("money.month")}</th>
              {columns.map(([field, label]) => (
                <th key={field} className="p-3 text-right font-semibold">{t(label)}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {months.map((m) => (
              <tr key={m.month}>
                <td className="p-3 whitespace-nowrap">{formatMonth(m.month)}</td>
                {columns.map(([field]) => (
                  <td key={field} className={`p-3 text-right whitespace-nowrap tabular-nums ${field === "net_cents" ? "font-semibold text-brand" : ""}`}>
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
                <td key={field} className="p-3 text-right whitespace-nowrap tabular-nums">{money(c.totals[field])}</td>
              ))}
            </tr>
          </tfoot>
        </table>
      </div>
    </>
  );
}
