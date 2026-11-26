"use client";

import { Armchair, BellRing, CircleCheck, Clock, Hourglass, XCircle } from "lucide-react";
import { useActionState, useEffect, useState, type ReactNode } from "react";

import { askForSeat, stopWaiting, waitForSeat, withdrawSeatRequest } from "@/app/learn/seat-actions";
import { useT } from "@eduzone/lib/i18n/client";
import type { SeatState } from "@eduzone/lib/types";
import { ActionButton } from "@eduzone/ui/action-button";
import { Button, ErrorText, Input, cx } from "@eduzone/ui";

type Tone = "success" | "warning" | "info" | "neutral";
const box: Record<Tone, string> = {
  success: "border-success/25 bg-success-bg text-success",
  warning: "border-warning/25 bg-warning-bg text-warning",
  info: "border-info/20 bg-info-bg text-info",
  neutral: "border-border bg-sunken text-foreground",
};

function Notice({ tone, icon, children, action }: { tone: Tone; icon: ReactNode; children: ReactNode; action?: ReactNode }) {
  return (
    <div className={cx("flex flex-col gap-2.5 rounded-ez border px-3.5 py-3 text-sm", box[tone])}>
      <p className="flex gap-2.5 leading-relaxed font-medium [&>svg]:mt-0.5 [&>svg]:size-4.5 [&>svg]:shrink-0">{icon}<span>{children}</span></p>
      {action}
    </div>
  );
}

/** What this student should know about their seat, and the one thing to do about it. Nothing to say: renders nothing.
 * `deadlines` are the state's times already written out (the server formats dates). */
export function SeatPanel({ classId, monthId, seat, waiting, deadlines }: {
  classId: string;
  monthId: string | null;
  seat: SeatState;
  waiting: boolean;
  deadlines: { kept: string | null; accepted: string | null };
}) {
  const t = useT();
  const r = seat.request;
  const note = r?.decision_note ? <span className="block font-normal text-foreground/80">{t("seat.teacherSaid", { note: r.decision_note })}</span> : null;

  if (seat.paying_until) return <HoldNotice until={seat.paying_until} />;
  if (seat.kept_until && deadlines.kept) {
    return <Notice tone="success" icon={<Armchair />}>{t("seat.kept", { when: deadlines.kept })}</Notice>;
  }
  if (r?.status === "approved" && deadlines.accepted) {
    return (
      <Notice tone="success" icon={<CircleCheck />}
              action={<ActionButton action={withdrawSeatRequest.bind(null, classId, monthId)} label={t("seat.withdraw")} small />}>
        {t("seat.accepted", { when: deadlines.accepted })}{note}
      </Notice>
    );
  }
  if (r?.status === "pending") {
    return (
      <Notice tone="info" icon={<Hourglass />}
              action={<ActionButton action={withdrawSeatRequest.bind(null, classId, monthId)} label={t("seat.withdraw")} small />}>
        {t("seat.requestPending")}
      </Notice>
    );
  }
  if (seat.problem === "SEAT_REQUEST_REQUIRED") {
    if (r?.status === "rejected") return <Notice tone="neutral" icon={<XCircle />}>{t("seat.rejected")}{note}</Notice>;
    return (
      <Notice tone={r?.status === "expired" ? "warning" : "info"} icon={<Armchair />}
              action={<AskForm action={askForSeat.bind(null, classId, monthId)} again={r?.status === "expired"} />}>
        {r?.status === "expired" ? t("seat.expired") : t("seat.panel.askBody")}
      </Notice>
    );
  }
  if (seat.problem === "CLASS_FULL" || seat.problem === "REGISTRATION_CLOSED") {
    return (
      <Notice tone="neutral" icon={waiting ? <BellRing /> : <Armchair />}
              action={waiting
                ? <ActionButton action={stopWaiting.bind(null, classId)} label={t("seat.stopWaiting")} small />
                : <ActionButton action={waitForSeat.bind(null, classId)} label={t("seat.notifyMe")} small />}>
        {waiting ? t("seat.waiting") : seat.problem === "CLASS_FULL" ? t("seat.panel.full") : t("seat.panel.closedBody")}
        {!waiting && <span className="block font-normal text-muted">{t("seat.notifyHint")}</span>}
      </Notice>
    );
  }
  return null;
}

/** The time left of a payment's hold, ticking. */
function HoldNotice({ until }: { until: string }) {
  const t = useT();
  const [left, setLeft] = useState<number | null>(null);        // unknown until the browser's clock is read
  useEffect(() => {
    const tick = () => setLeft(Math.max(0, Math.ceil((new Date(until).getTime() - Date.now()) / 1000)));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [until]);
  if (left === 0) return <Notice tone="warning" icon={<Clock />}>{t("seat.heldEnded")}</Notice>;
  const time = left === null ? "…" : `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
  return <Notice tone="info" icon={<Clock />}><span className="tabular-nums" role="timer">{t("seat.held", { time })}</span></Notice>;
}

function AskForm({ action, again }: { action: (s: { error?: string }, fd: FormData) => Promise<{ error?: string }>; again: boolean }) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  return (
    <form action={submit} className="flex flex-col gap-2 sm:flex-row sm:items-start">
      <div className="min-w-0 flex-1">
        <Input name="note" maxLength={500} placeholder={t("seat.askNote")} aria-label={t("seat.askNote")} />
        <ErrorText>{state.error}</ErrorText>
      </div>
      <Button loading={pending} className="shrink-0">{t(again ? "seat.askAgain" : "seat.askButton")}</Button>
    </form>
  );
}
