"use client";

import { useActionState, useState } from "react";

import { useT } from "@eduzone/lib/i18n/client";
import { Button, Input } from "@eduzone/ui";

import type { SeatFormState } from "../classes/seat-actions";

type Action = (state: SeatFormState, fd: FormData) => Promise<SeatFormState>;

/** Accept and / or decline a seat request, with an optional note the student reads. */
export function SeatDecisionForm({ approve, reject, approveLabel, rejectLabel, confirmReject }: {
  approve?: Action;
  reject?: Action;
  approveLabel?: string;
  rejectLabel?: string;
  confirmReject?: string;
}) {
  const t = useT();
  const [noting, setNoting] = useState(false);
  const [state, submit, pending] = useActionState<SeatFormState, FormData>(async (prev, fd) => {
    const action = fd.get("decision") === "reject" ? reject : approve;
    return action ? action(prev, fd) : prev;
  }, {});
  return (
    <form
      action={submit}
      onSubmit={(e) => {
        const value = (e.nativeEvent as SubmitEvent).submitter?.getAttribute("value");
        if (value === "reject" && confirmReject && !window.confirm(confirmReject)) e.preventDefault();
      }}
      className="flex flex-col gap-2 sm:items-end"
    >
      {noting && <Input name="note" maxLength={500} placeholder={t("seatRequests.note")} aria-label={t("seatRequests.note")} autoFocus className="sm:w-72" />}
      <div className="flex flex-wrap gap-2">
        {!noting && <Button type="button" variant="ghost" size="sm" onClick={() => setNoting(true)}>{t("seatRequests.addNote")}</Button>}
        {approve && <Button name="decision" value="approve" size="sm" loading={pending}>{approveLabel}</Button>}
        {reject && <Button name="decision" value="reject" variant="danger" size="sm" loading={pending}>{rejectLabel}</Button>}
      </div>
      {state.error && <p role="alert" className="max-w-xs text-xs font-medium text-danger sm:text-right">{state.error}</p>}
    </form>
  );
}
