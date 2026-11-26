import { ChevronRight, MessageSquareText } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { SiteShell } from "@/components/shell";
import type { Schema } from "@eduzone/api-client";
import { api } from "@/lib/api";
import { deadline } from "@/lib/seats";
import { getMe } from "@/lib/session";
import { formatDateTime, formatMonth } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import type { MyRequest } from "@eduzone/lib/types";
import { EmptyState, ErrorText, PageHeader, StatusPill, type PillState } from "@eduzone/ui";

const pill: Record<MyRequest["status"], PillState> = {
  pending: "pending",
  approved: "unpaid",
  rejected: "closed",
  fulfilled: "paid",
  cancelled: "closed",
};

const seatPill: Record<"pending" | "approved" | "rejected" | "expired", PillState> = {
  pending: "pending", approved: "unpaid", rejected: "closed", expired: "closed",
};

/** What the student asked teachers for: seats, classes to be told about, and past months. */
export default async function RequestsPage() {
  if (!(await getMe())) redirect("/login?next=/learn/requests");
  const [res, seatsRes, waitsRes] = await Promise.all([
    api<MyRequest[]>("/learn/requests"),
    api<Schema<"MySeatRequestRow">[]>("/learn/seat-requests"),
    api<Schema<"MySeatWait">[]>("/learn/seat-waits"),
  ]);
  const seats = seatsRes.ok ? seatsRes.data : [];
  const waits = waitsRes.ok ? waitsRes.data : [];

  return (
    <SiteShell width="md">
      <PageHeader eyebrow={t("learn.eyebrow")} title={t("requests.pageTitle")} description={t("learn.requests.subtitle")} />
      {seats.length > 0 && (
        <Group title={t("seat.requests.title")}>
          {seats.map((r) => (
            <Row key={r.id} href={`/learn/classes/${r.class_id}`} title={r.month_start ? `${r.class_title} · ${formatMonth(r.month_start)}` : r.class_title}
                 meta={`${r.org.name} · ${formatDateTime(r.created_at)}`}
                 note={r.status === "approved" && r.held_until ? t("seat.accepted", { when: deadline(r.held_until) })
                   : r.decision_note ? t("seat.teacherSaid", { note: r.decision_note }) : null}
                 pill={<StatusPill state={seatPill[r.status]}>{t(`seat.requests.status.${r.status}`)}</StatusPill>} />
          ))}
        </Group>
      )}
      {waits.length > 0 && (
        <Group title={t("seat.requests.waitTitle")}>
          {waits.map((w) => (
            <Row key={w.class_id} href={`/learn/classes/${w.class_id}`} title={w.class_title} meta={w.org.name}
                 pill={<StatusPill state={w.available ? "unpaid" : "pending"}>{t(w.available ? "seat.requests.available" : "seat.requests.notYet")}</StatusPill>} />
          ))}
        </Group>
      )}
      {(seats.length > 0 || waits.length > 0) && res.ok && res.data.length > 0 && (
        <h2 className="font-display text-xl font-semibold">{t("learn.requests.title")}</h2>
      )}
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.length === 0 && seats.length === 0 && waits.length === 0 && (
        <EmptyState icon={<MessageSquareText />} title={t("learn.requests.empty")} body={t("learn.requests.emptyBody")} />
      )}
      {res.ok && res.data.length > 0 && (
        <ul className="overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-sm">
          {res.data.map((r, i) => (
            <li key={r.id} className="ez-rise border-b border-border last:border-0" style={{ "--i": i } as React.CSSProperties}>
              <Link href={`/learn/classes/${r.class_id}`} className="group flex items-center gap-4 p-4 hover:bg-sunken/50 sm:p-5">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold">{r.class_title} · {formatMonth(r.month_start)}</p>
                  <p className="truncate text-sm text-muted">{r.org.name} · {formatDateTime(r.created_at)}</p>
                  {r.decision_note && (
                    <p className="mt-1 text-sm text-foreground/80">{t("learn.requests.teacherSaid", { note: r.decision_note })}</p>
                  )}
                </div>
                <StatusPill state={pill[r.status]}>{t(`learn.requests.status.${r.status}`)}</StatusPill>
                <ChevronRight className="hidden size-5 text-subtle group-hover:text-brand sm:block" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </SiteShell>
  );
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="font-display text-xl font-semibold">{title}</h2>
      <ul className="overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-sm">{children}</ul>
    </section>
  );
}

function Row({ href, title, meta, note, pill }: { href: string; title: string; meta: string; note?: string | null; pill: React.ReactNode }) {
  return (
    <li className="border-b border-border last:border-0">
      <Link href={href} className="group flex flex-col gap-3 p-4 hover:bg-sunken/50 sm:flex-row sm:items-center sm:p-5">
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{title}</p>
          <p className="text-sm text-muted">{meta}</p>
          {note && <p className="mt-1 text-sm text-foreground/80">{note}</p>}
        </div>
        <span className="self-start sm:self-auto">{pill}</span>
        <ChevronRight className="hidden size-5 text-subtle group-hover:text-brand sm:block" />
      </Link>
    </li>
  );
}
