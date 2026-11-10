"use client";

import { useActionState } from "react";

import { useT } from "@eduzone/lib/i18n/client";
import { Button, ErrorText, Field, Input, Textarea } from "@eduzone/ui";

import type { ActionState as FormState } from "@eduzone/ui";

type Action = (state: FormState, fd: FormData) => Promise<FormState>;

/** Approve (refund now) or refuse with a note the student reads. */
export function RefundDecisionForm({ action, amount }: { action: Action; amount: string }) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  return (
    <form
      action={submit}
      onSubmit={(e) => {
        const decision = (e.nativeEvent as SubmitEvent).submitter?.getAttribute("value");
        const ask = decision === "approve" ? t("platform.refunds.confirmApprove", { amount }) : t("platform.refunds.confirmReject");
        if (!window.confirm(ask)) e.preventDefault();
      }}
      className="flex flex-col gap-3"
    >
      <Field label={t("platform.refunds.note")} hint={t("platform.refunds.noteHint")}>
        <Textarea name="note" rows={3} maxLength={1000} />
      </Field>
      <ErrorText>{state.error}</ErrorText>
      <div className="flex flex-wrap gap-2">
        <Button name="decision" value="approve" loading={pending}>{t("platform.refunds.approve", { amount })}</Button>
        <Button name="decision" value="reject" variant="danger" loading={pending}>{t("platform.refunds.reject")}</Button>
      </div>
    </form>
  );
}

/** Refunded by hand in the gateway's portal: record its reference to finish the refund here. */
export function ManualRefundForm({ action }: { action: Action }) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  return (
    <form action={submit} className="flex flex-col gap-3">
      <Field label={t("platform.refunds.gatewayRef")} hint={t("platform.refunds.gatewayRefHint")}>
        <Input name="gateway_refund_ref" required minLength={2} maxLength={120} className="font-mono" />
      </Field>
      <ErrorText>{state.error}</ErrorText>
      <Button type="submit" variant="secondary" loading={pending} className="self-start">{t("platform.refunds.markProcessed")}</Button>
    </form>
  );
}
