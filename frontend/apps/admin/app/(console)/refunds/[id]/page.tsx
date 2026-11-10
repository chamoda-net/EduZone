import { AlertTriangle } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import type { Schema } from "@eduzone/api-client";
import { ActionButton } from "@eduzone/ui/action-button";
import { Badge, Card, CardTitle, DataList, ErrorText, buttonClass } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatDateTime, formatMoney } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";

import { decideRefund, markRefundProcessed, retryRefund } from "../../../actions";
import { ManualRefundForm, RefundDecisionForm } from "./forms";

type Detail = Schema<"PlatformRefundDetail">;

const tone = { requested: "warning", approved: "info", processed: "success", rejected: "neutral" } as const;

/** One refund: the student's request against the rule, then the decision or what the gateway still needs. */
export default async function RefundPage({ params }: PageProps<"/refunds/[id]">) {
  const { id } = await params;
  const res = await api<Detail>(`/platform/refunds/${id}`);
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    return <ErrorText>{errorText(t, res.error)}</ErrorText>;
  }
  const r = res.data;
  const amount = formatMoney(r.amount_cents, r.currency);
  const flags = [
    [t("platform.refunds.checkWindow"), r.in_window],
    [t("platform.refunds.checkProgress", { percent: r.progress_percent }), r.progress_percent < 30],
    [t("platform.refunds.checkCertificate"), !r.certificate],
    [t("platform.refunds.checkHistory", { count: r.recent_refunds }), r.recent_refunds < 3],
  ] as const;
  const waiting = r.status === "approved";

  return (
    <>
      <Link href="/refunds" className={`${buttonClass.link} text-sm`}>← {t("platform.refunds.back")}</Link>
      <header className="flex flex-col gap-1">
        <h1 className="flex flex-wrap items-center gap-3 font-display text-3xl font-semibold">
          {amount}
          <Badge tone={tone[r.status as keyof typeof tone] ?? "neutral"}>{t(`platform.refunds.status.${r.status as keyof typeof tone}`)}</Badge>
        </h1>
        <p className="text-sm text-muted">
          {r.course_title} · {t("platform.refunds.asked", { date: formatDateTime(r.created_at) })}
          {r.auto_approved && ` · ${t("platform.refunds.auto")}`}
        </p>
      </header>

      {waiting && (
        <div role="status" className="flex flex-col gap-4 rounded-ez-lg border border-danger/25 bg-danger-bg p-4">
          <div className="flex gap-3">
            <AlertTriangle className="mt-0.5 size-5 shrink-0 text-danger" aria-hidden />
            <div>
              <p className="font-semibold text-danger">{t("platform.refunds.waitingTitle")}</p>
              <p className="text-sm text-foreground/80">{r.failure_reason ?? t("platform.refunds.waitingBody")}</p>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-[auto_1fr] sm:items-start">
            <ActionButton variant="danger" action={retryRefund.bind(null, r.id)} label={t("platform.refunds.retry")}
                          done={t("platform.refunds.done")} />
            <ManualRefundForm action={markRefundProcessed.bind(null, r.id)} />
          </div>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
        <Card>
          <DataList items={[
            [t("orgPayments.student"), <Link key="s" href={`/users/${r.student_user_id}`} className="text-brand hover:underline">{r.student_name}</Link>],
            [t("auth.phone"), r.student_phone ?? "—"],
            [t("platform.refunds.organization"), <Link key="o" href={`/tenants/${r.tenant_id}`} className="text-brand hover:underline">{r.tenant_name}</Link>],
            [t("platform.refunds.order"), <span key="n" className="font-mono text-sm">{r.order_no}</span>],
            [t("platform.refunds.paid"), r.paid_at ? formatDateTime(r.paid_at) : "—"],
            [t("platform.refunds.gateway"), <span key="g" className="font-mono text-sm">{r.gateway} {r.gateway_payment_ref ?? ""}</span>],
            ...(r.gateway_refund_ref ? [[t("platform.refunds.gatewayRef"), <span key="r" className="font-mono text-sm">{r.gateway_refund_ref}</span>] as [string, React.ReactNode]] : []),
          ]} />
        </Card>

        <Card className="flex flex-col gap-4">
          <CardTitle>{t("platform.refunds.request")}</CardTitle>
          <blockquote className="rounded-ez border-l-4 border-brand/30 bg-sunken/60 px-4 py-3 text-sm whitespace-pre-line">{r.reason}</blockquote>
          <ul className="flex flex-col gap-1.5 text-sm">
            {flags.map(([label, ok]) => (
              <li key={label} className="flex items-center gap-2">
                <span className={ok ? "text-success" : "text-danger"} aria-hidden>{ok ? "✓" : "✕"}</span>
                <span className={ok ? "" : "font-semibold text-danger"}>{label}</span>
              </li>
            ))}
          </ul>
          {r.decision_note && (
            <p className="text-sm"><span className="font-semibold">{t("platform.refunds.note")}:</span> {r.decision_note}</p>
          )}
          {r.status === "requested" && <RefundDecisionForm action={decideRefund.bind(null, r.id)} amount={amount} />}
        </Card>
      </div>
    </>
  );
}
