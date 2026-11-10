import { ArrowRight, Mail, Percent } from "lucide-react";
import Link from "next/link";

import type { Schema } from "@eduzone/api-client";
import { ActionButton } from "@eduzone/ui/action-button";
import { Badge, Card, CardTitle, EmptyState, ErrorText, PageHeader } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import type { PlatformTenant } from "@eduzone/lib/types";

import { cancelCommissionChange, scheduleCommissionChange } from "../../actions";
import { ScheduleForm } from "./form";

type Overview = Schema<"CommissionOverview">;
type Change = Schema<"CommissionChange">;

const tone = { scheduled: "info", applied: "success", cancelled: "neutral" } as const;
const pct = (bps: number) => `${bps / 100}%`;

/** Commission per product type: the platform defaults, changes scheduled with notice, and what was applied. */
export default async function CommissionPage() {
  const [res, tenants] = await Promise.all([api<Overview>("/platform/commission"), api<PlatformTenant[]>("/platform/tenants")]);
  if (!res.ok) return <ErrorText>{errorText(t, res.error)}</ErrorText>;
  const o = res.data;
  const scheduled = o.changes.filter((c) => c.status === "scheduled");
  const past = o.changes.filter((c) => c.status !== "scheduled");

  return (
    <>
      <PageHeader title={t("platform.nav.commission")} description={t("platform.commission.body", { days: o.notice_days })} />
      <div className="grid gap-3 sm:grid-cols-2">
        {o.rates.map((r) => (
          <Card key={r.kind} className="flex items-center gap-4">
            <span className="grid size-11 place-items-center rounded-full bg-brand-50 text-brand"><Percent className="size-5" /></span>
            <div>
              <p className="text-sm text-muted">{t(`platform.commission.kind.${r.kind as "course"}`)}</p>
              <p className="font-display text-3xl font-semibold tabular-nums">{pct(r.commission_bps)}</p>
              <p className="text-xs text-muted">{t("platform.commission.defaultSince", { date: formatDateTime(r.updated_at) })}</p>
            </div>
          </Card>
        ))}
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_26rem]">
        <section className="flex min-w-0 flex-col gap-4">
          <h2 className="font-display text-xl font-semibold">{t("platform.commission.upcoming")}</h2>
          {scheduled.length === 0
            ? <EmptyState icon={<Percent />} title={t("platform.commission.none")} body={t("platform.commission.noneBody")} />
            : <ul className="flex flex-col gap-3">{scheduled.map((c) => <ChangeRow key={c.id} c={c} />)}</ul>}
          {past.length > 0 && (
            <>
              <h2 className="mt-2 font-display text-xl font-semibold">{t("platform.commission.history")}</h2>
              <ul className="flex flex-col gap-3">{past.map((c) => <ChangeRow key={c.id} c={c} />)}</ul>
            </>
          )}
        </section>
        <Card className="lg:sticky lg:top-6">
          <CardTitle>{t("platform.commission.new")}</CardTitle>
          <ScheduleForm action={scheduleCommissionChange} noticeDays={o.notice_days}
                        tenants={tenants.ok ? tenants.data.map((x) => ({ id: x.id, name: x.name })) : []} />
        </Card>
      </div>
    </>
  );
}

function ChangeRow({ c }: { c: Change }) {
  const emails = c.notified.reduce((n, x) => n + x.emails.length, 0);
  return (
    <li className="rounded-ez-lg border border-border bg-surface p-4 shadow-ez-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 text-sm">
            <Badge tone={tone[c.status as keyof typeof tone] ?? "neutral"}>{t(`platform.commission.status.${c.status as keyof typeof tone}`)}</Badge>
            <span className="font-semibold">{t(`platform.commission.kind.${c.kind as "course"}`)}</span>
            <span className="text-muted">·</span>
            {c.tenant_id
              ? <Link href={`/tenants/${c.tenant_id}`} className="text-brand hover:underline">{c.tenant_name}</Link>
              : <span className="text-muted">{t("platform.commission.scopes.platform")}</span>}
          </p>
          <p className="mt-1.5 flex items-center gap-2 font-display text-2xl font-semibold tabular-nums">
            {pct(c.old_bps)} <ArrowRight className="size-5 text-muted" /> <span className={c.new_bps > c.old_bps ? "text-danger" : "text-success"}>{pct(c.new_bps)}</span>
          </p>
          <p className="mt-1 text-sm text-foreground/85">{c.reason}</p>
        </div>
        <div className="text-right text-sm">
          <p className="font-semibold">{formatDateTime(c.effective_at)}</p>
          <p className="text-xs text-muted">{t("platform.commission.announced", { date: formatDateTime(c.announced_at), by: c.created_by_name })}</p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
        <details className="text-sm">
          <summary className="inline-flex cursor-pointer items-center gap-1.5 text-muted hover:text-foreground">
            <Mail className="size-4" />{t("platform.commission.notified", { orgs: c.notified.length, emails })}
          </summary>
          <ul className="mt-2 flex flex-col gap-1 text-xs text-muted">
            {c.notified.map((n) => <li key={n.tenant_id}><span className="font-semibold text-foreground">{n.tenant_name}</span>: {n.emails.join(", ") || "—"}</li>)}
          </ul>
        </details>
        {c.status === "scheduled" && (
          <ActionButton variant="danger" action={cancelCommissionChange.bind(null, c.id)} label={t("platform.commission.cancel")}
                        done={t("platform.commission.cancelled")} confirm={t("platform.commission.confirmCancel")} />
        )}
      </div>
    </li>
  );
}
