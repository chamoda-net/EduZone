import { Armchair, Inbox } from "lucide-react";
import Link from "next/link";

import type { Schema } from "@eduzone/api-client";
import { ActionButton } from "@eduzone/ui/action-button";
import { Badge, EmptyState, ErrorText, FilterChips, cx } from "@eduzone/ui";
import { api } from "@/lib/api";
import { deadline } from "@/lib/seats";
import { teachHref } from "@/lib/workspace";
import { formatDateTime, formatMonth } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import type { LateRequest } from "@eduzone/lib/types";

import { decideRequest } from "../classes/actions";
import { decideSeatRequest } from "../classes/seat-actions";
import { SeatDecisionForm } from "./seat-decision";

type SeatRequest = Schema<"SeatRequestRow">;

const TABS = ["pending", "approved", "rejected", "fulfilled"] as const;
type Tab = (typeof TABS)[number];
const tone: Record<Tab, string> = { pending: "draft", approved: "upcoming", rejected: "archived", fulfilled: "published" };

const SEAT_TABS = ["pending", "approved", "expired", "rejected", "used"] as const;
type SeatTab = (typeof SEAT_TABS)[number];
const seatTone: Record<SeatTab, string> = { pending: "warning", approved: "gold", expired: "neutral", rejected: "neutral", used: "success" };

/** What students ask for: past months (buying a closed one) and seats (classes whose new students ask first). */
export default async function RequestsPage({ searchParams }: PageProps<"/teach/[tenant]/requests">) {
  const base = await teachHref();
  const sp = await searchParams;
  const seats = sp.type === "seats";
  const [monthsWaiting, seatsWaiting] = await Promise.all([
    api<LateRequest[]>("~/late-requests?status=pending"),
    api<SeatRequest[]>("~/seat-requests?status=pending"),
  ]);
  const count = (r: typeof monthsWaiting | typeof seatsWaiting) => (r.ok ? r.data.length || undefined : undefined);

  return (
    <>
      <h1 className="font-display text-3xl font-semibold sm:text-4xl">{t("requests.pageTitle")}</h1>
      <nav className="flex gap-6 border-b border-border text-sm font-semibold">
        {([["months", `${base}/requests`, !seats, count(monthsWaiting)], ["seats", `${base}/requests?type=seats`, seats, count(seatsWaiting)]] as const).map(
          ([key, href, active, n]) => (
            <Link key={key} href={href} aria-current={active ? "page" : undefined}
                  className={cx("-mb-px inline-flex min-h-11 items-center gap-2 border-b-2 px-1", active ? "border-brand text-foreground" : "border-transparent text-muted hover:text-foreground")}>
              {t(`requests.tab.${key}`)}
              {n && <span className="rounded-full bg-gold px-2 py-0.5 text-xs text-brand-950 tabular-nums">{n}</span>}
            </Link>
          ),
        )}
      </nav>
      {seats ? <SeatRequests base={base} status={sp.status} /> : <MonthRequests base={base} status={sp.status} />}
    </>
  );
}

async function SeatRequests({ base, status: raw }: { base: string; status: string | string[] | undefined }) {
  const status: SeatTab = SEAT_TABS.includes(raw as SeatTab) ? (raw as SeatTab) : "pending";
  const res = await api<SeatRequest[]>(`~/seat-requests?status=${status}`);
  return (
    <>
      <FilterChips items={SEAT_TABS.map((s) => ({
        href: s === "pending" ? `${base}/requests?type=seats` : `${base}/requests?type=seats&status=${s}`,
        label: t(`seatRequests.status.${s}`), active: s === status,
      }))} />
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.length === 0 && (
        <EmptyState icon={<Armchair />} title={t("seatRequests.empty")} body={status === "pending" ? t("seatRequests.emptyBody") : undefined} />
      )}
      {res.ok && res.data.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-ez-lg border border-border bg-surface">
          {res.data.map((r) => (
            <li key={r.id} className="flex flex-col gap-3 p-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <p className="font-medium">
                  {r.student_name} <span className="text-sm font-normal text-muted">{r.student_phone}</span>
                </p>
                <p className="text-sm">
                  <Link href={`${base}/classes/${r.class_id}`} className="text-brand hover:underline">{r.class_title}</Link>
                  {r.month_start && <> · {formatMonth(r.month_start)}</>}
                </p>
                {r.student_note && <p className="mt-1 text-sm text-muted">“{r.student_note}”</p>}
                {r.decision_note && <p className="mt-1 text-sm text-foreground/80">{t("seatRequests.yourNote", { note: r.decision_note })}</p>}
                <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                  <span>{formatDateTime(r.created_at)}</span>
                  {r.seats_free !== null && (
                    <span className={cx("font-semibold", r.seats_free === 0 ? "text-danger" : "text-success")}>{t("seatRequests.seatsFree", { count: r.seats_free })}</span>
                  )}
                  {r.status === "approved" && r.held_until && <span className="font-semibold text-gold-strong">{t("seatRequests.payBy", { when: deadline(r.held_until) })}</span>}
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap items-start gap-2">
                {r.status === "pending" && (
                  <SeatDecisionForm approve={decideSeatRequest.bind(null, r.id, "approve")} reject={decideSeatRequest.bind(null, r.id, "reject")}
                                    approveLabel={t("seatRequests.accept")} rejectLabel={t("seatRequests.decline")} />
                )}
                {r.status === "approved" && (
                  <SeatDecisionForm reject={decideSeatRequest.bind(null, r.id, "reject")} rejectLabel={t("seatRequests.takeBack")}
                                    confirmReject={t("seatRequests.confirmTakeBack")} />
                )}
                {(r.status === "expired" || r.status === "rejected") && (
                  <SeatDecisionForm approve={decideSeatRequest.bind(null, r.id, "approve")}
                                    approveLabel={t(r.status === "expired" ? "seatRequests.acceptAgain" : "seatRequests.acceptAfterAll")} />
                )}
                {r.status === "used" && <Badge tone={seatTone.used}>{t("seatRequests.status.used")}</Badge>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

/** Students asking to buy months that are already closed. Approval lets them pay (step 7). */
async function MonthRequests({ base, status: raw }: { base: string; status: string | string[] | undefined }) {
  const status: Tab = TABS.includes(raw as Tab) ? (raw as Tab) : "pending";
  const res = await api<LateRequest[]>(`~/late-requests?status=${status}`);
  return (
    <>
      <FilterChips items={TABS.map((s) => ({
        href: s === "pending" ? `${base}/requests` : `${base}/requests?status=${s}`, label: t(`requests.status.${s}`), active: s === status,
      }))} />
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.length === 0 && <EmptyState icon={<Inbox />} title={t("requests.empty")} />}
      {res.ok && res.data.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-ez-lg border border-border bg-surface">
          {res.data.map((r) => (
            <li key={r.id} className="flex flex-col gap-2 p-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <p className="font-medium">
                  {r.student_name} <span className="text-sm font-normal text-muted">{r.student_phone}</span>
                </p>
                <p className="text-sm">
                  <Link href={`${base}/classes/${r.class_id}`} className="text-brand hover:underline">{r.class_title}</Link>
                  {" · "}
                  {formatMonth(r.month_start)}
                </p>
                {r.student_note && <p className="mt-1 text-sm text-muted">“{r.student_note}”</p>}
                <p className="mt-1 text-xs text-muted">{formatDateTime(r.created_at)}</p>
              </div>
              {r.status === "pending" ? (
                <div className="flex gap-2">
                  <ActionButton action={decideRequest.bind(null, r.id, "approve")} label={t("requests.approve")} variant="primary" small />
                  <ActionButton action={decideRequest.bind(null, r.id, "reject")} label={t("requests.reject")} variant="danger" small />
                </div>
              ) : (
                <Badge tone={tone[r.status as Tab] ?? "archived"}>{t(`requests.status.${r.status as Tab}`)}</Badge>
              )}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
