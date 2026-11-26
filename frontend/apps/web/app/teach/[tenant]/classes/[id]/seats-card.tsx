import { Armchair, BellRing, Check, Clock, CreditCard, UserCheck } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import type { Schema } from "@eduzone/api-client";
import { api } from "@/lib/api";
import { deadline, lastDay } from "@/lib/seats";
import { teachHref } from "@/lib/workspace";
import { formatMonth, isoToColomboLocal } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import type { ClassItem, Month, Registration } from "@eduzone/lib/types";
import { ActionButton } from "@eduzone/ui/action-button";
import { Alert, Badge, Card, ErrorText, cx, type BadgeTone } from "@eduzone/ui";

import { keepSeat, releaseSeat, saveRenewUntil, saveSeatSettings } from "../seat-actions";
import { KeepSeatDialog, RenewDateForm, SeatSettingsForm } from "./seat-forms";

type Seats = Schema<"SeatsOut">;
type Kind = Seats["seats"][number]["kind"];

const KINDS = ["access", "paying", "accepted", "kept"] as const;
const style: Record<Kind, { box: string; icon: ReactNode; tone: BadgeTone }> = {
  access: { box: "bg-success-bg text-success border-success/20", icon: <Check />, tone: "success" },
  paying: { box: "bg-info-bg text-info border-info/20", icon: <CreditCard />, tone: "info" },
  accepted: { box: "bg-gold-100 text-gold-strong border-gold/30", icon: <UserCheck />, tone: "gold" },
  kept: { box: "bg-warning-bg text-warning border-warning/20", icon: <Clock />, tone: "warning" },
};
const registrationTone: Record<Registration, BadgeTone> = { open: "success", ask: "info", closed: "neutral" };

/** More seats than this are drawn as a bar instead of one box each. */
const MAX_BOXES = 60;

/** Seats on the class page: how many are taken and why, who may join, and what staff can do about one seat. Hidden until
 * seats are switched on (SEATS_ENABLED), unless the class already uses them. */
export async function SeatsCard({ c, months, month }: { c: ClassItem; months: Month[]; month: Month | null }) {
  const used = c.seat_limit !== null || c.registration !== "open" || c.registration_after_start !== null;
  if (!c.seats_enabled && !used) return null;
  const monthly = c.pricing_model === "monthly";
  const base = await teachHref();
  const res = monthly && !month ? null : await api<Seats>(`~/classes/${c.id}/seats${month ? `?month_id=${month.id}` : ""}`);
  const s = res?.ok ? res.data : null;

  return (
    <Card className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-xl font-semibold">{t("seats.title")}</h2>
          <p className="text-sm text-muted">{t("seats.lead")}</p>
        </div>
        {s && <Badge tone={registrationTone[s.registration]} dot>{t(`seats.registrationBadge.${s.registration}`)}</Badge>}
      </div>

      {monthly && months.length > 1 && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted">{t("seats.forMonth")}</span>
          {months.map((m) => (
            <Link key={m.id} href={`${base}/classes/${c.id}?month=${m.id}`} scroll={false}
                  aria-current={m.id === month?.id ? "true" : undefined}
                  className={cx("rounded-full border px-3 py-1", m.id === month?.id ? "border-brand-800 bg-brand-800 text-on-brand shadow-ez-sm" : "border-border")}>
              {formatMonth(m.month_start)}
            </Link>
          ))}
        </div>
      )}
      {monthly && !month && <p className="text-sm text-muted">{t("seats.noMonths")}</p>}
      {res && !res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {s && <SeatMap s={s} />}
      {s && s.over_by > 0 && <Alert tone="warning" title={t("seats.overTitle", { count: s.over_by })}>{t("seats.overBody")}</Alert>}
      {s && (s.waiting > 0 || s.registration === "ask") && (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
          {s.waiting > 0 && (
            <span className="inline-flex items-center gap-2 text-muted"><BellRing className="size-4 text-gold-strong" />{t("seats.waiting", { count: s.waiting })}</span>
          )}
          <Link href={`${base}/requests?type=seats`} className="font-semibold text-brand hover:underline">{t("seats.requestsLink")}</Link>
        </div>
      )}
      {s && month && month.status === "open" && month.renew_until && c.seat_limit !== null && (
        <RenewDateForm action={saveRenewUntil.bind(null, c.id, month.id)} value={lastDay(month.renew_until)}
                       passed={new Date(month.renew_until) <= new Date()} lapsed={s.lapsed.filter((l) => !l.released).length} />
      )}
      {s && s.seats.length > 0 && <SeatList s={s} classId={c.id} month={month} />}
      {s && s.lapsed.length > 0 && month && <LapsedList s={s} classId={c.id} month={month} />}

      <details open={c.seat_limit === null && !used} className="rounded-ez border border-border px-4 py-3 [&[open]]:pb-5">
        <summary className="cursor-pointer text-sm font-semibold text-brand">{t("seats.settings")}</summary>
        <div className="pt-4"><SeatSettingsForm action={saveSeatSettings.bind(null, c.id)} c={c} /></div>
      </details>
    </Card>
  );
}

function SeatMap({ s }: { s: Seats }) {
  if (s.limit === null) return <p className="text-sm text-muted">{t("seats.noLimit", { taken: s.taken })}</p>;
  const free = s.free ?? 0;
  const counts = KINDS.map((k) => [k, s.seats.filter((x) => x.kind === k).length] as const);
  return (
    <div className="flex flex-col gap-3">
      <p className="font-display text-2xl font-semibold tabular-nums">{t("seats.taken", { taken: s.taken, limit: s.limit })}</p>
      {Math.max(s.limit, s.taken) <= MAX_BOXES ? (
        <div aria-hidden className="flex flex-wrap gap-2">
          {s.seats.map((x) => (
            <span key={x.member_id} title={x.full_name} className={cx("grid size-10 place-items-center rounded-ez border [&>svg]:size-4.5", style[x.kind].box)}>
              {style[x.kind].icon}
            </span>
          ))}
          {Array.from({ length: free }, (_, i) => (
            <span key={i} className="grid size-10 place-items-center rounded-ez border border-dashed border-border-strong text-subtle [&>svg]:size-4.5"><Armchair /></span>
          ))}
        </div>
      ) : (
        <div aria-hidden className="h-3 overflow-hidden rounded-full bg-sunken">
          <div className="h-full rounded-full bg-brand" style={{ width: `${Math.min(100, (s.taken / s.limit) * 100)}%` }} />
        </div>
      )}
      <ul className="flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-muted">
        {counts.filter(([, n]) => n > 0).map(([k, n]) => (
          <li key={k} className="inline-flex items-center gap-1.5">
            <span aria-hidden className={cx("grid size-5 place-items-center rounded border [&>svg]:size-3", style[k].box)}>{style[k].icon}</span>
            {t(`seats.legend.${k}`)}: <b className="text-foreground tabular-nums">{n}</b>
          </li>
        ))}
        <li className="inline-flex items-center gap-1.5">
          <span aria-hidden className="grid size-5 place-items-center rounded border border-dashed border-border-strong [&>svg]:size-3"><Armchair /></span>
          {t("seats.legend.free")}: <b className="text-foreground tabular-nums">{free}</b>
        </li>
      </ul>
    </div>
  );
}

/** A week from today, and the latest day a seat can be kept (the API allows 60 days). */
function keepDays(current: string | null): { defaultDay: string; maxDay: string } {
  const day = (n: number) => isoToColomboLocal(new Date(Date.now() + n * 86_400_000).toISOString()).slice(0, 10);
  const start = current && lastDay(current) > day(7) ? lastDay(current) : day(7);
  return { defaultDay: start, maxDay: day(59) };
}

function SeatList({ s, classId, month }: { s: Seats; classId: string; month: Month | null }) {
  return (
    <details open={s.seats.length <= 12} className="flex flex-col">
      <summary className="cursor-pointer text-sm font-semibold">{t("seats.students")} ({s.seats.length})</summary>
      <ul className="mt-2 divide-y divide-border">
        {s.seats.map((x) => (
          <li key={x.member_id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
            <div className="min-w-0">
              <p className="font-medium">{x.full_name}</p>
              <p className="text-sm text-muted">{x.phone}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={style[x.kind].tone}>
                {x.kind === "access" || !x.held_until ? t("seats.kind.access") : t(`seats.kind.${x.kind}`, { when: deadline(x.held_until) })}
              </Badge>
              {x.kind === "kept" && month && (
                <>
                  <KeepSeatDialog action={keepSeat.bind(null, classId, month.id, x.member_id)} name={x.full_name} label={t("seats.keepLonger")} {...keepDays(x.held_until)} />
                  <ActionButton action={releaseSeat.bind(null, classId, month.id, x.member_id)} label={t("seats.release")} variant="danger" small
                                confirm={t("seats.confirmRelease")} done={t("seats.done")} />
                </>
              )}
            </div>
          </li>
        ))}
      </ul>
    </details>
  );
}

function LapsedList({ s, classId, month }: { s: Seats; classId: string; month: Month }) {
  return (
    <div>
      <h3 className="text-sm font-semibold">{t("seats.lapsedTitle")}</h3>
      <ul className="mt-1 divide-y divide-border">
        {s.lapsed.map((x) => (
          <li key={x.member_id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
            <div className="min-w-0">
              <p className="font-medium">{x.full_name}</p>
              <p className="text-sm text-muted">{x.phone}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {x.released && <Badge tone="neutral">{t("seats.released")}</Badge>}
              {month.status === "open" && (
                <KeepSeatDialog action={keepSeat.bind(null, classId, month.id, x.member_id)} name={x.full_name} label={t("seats.keep")} {...keepDays(null)} />
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
