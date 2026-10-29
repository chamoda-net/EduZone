"use client";

import { useActionState } from "react";

import { ErrorText, Field, Input, buttonClass } from "@/components/ui";
import { useT } from "@/lib/i18n/client";

import type { FormState } from "../../../../org/classes/actions";

export function PayoutForm({ action, maxRupees }: {
  action: (state: FormState, fd: FormData) => Promise<FormState>;
  maxRupees: string;
}) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  return (
    <form
      key={state.at}
      action={submit}
      onSubmit={(e) => {
        if (!window.confirm(t("platform.payout.confirm"))) e.preventDefault();
      }}
      className="flex flex-col gap-3"
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("platform.payout.amount")}>
          <Input name="amount" inputMode="decimal" required placeholder={maxRupees} />
        </Field>
        <Field label={t("platform.payout.reference")}>
          <Input name="bank_reference" required minLength={3} maxLength={100} />
        </Field>
        <Field label={t("platform.payout.from")}>
          <Input name="period_start" type="date" required />
        </Field>
        <Field label={t("platform.payout.to")}>
          <Input name="period_end" type="date" required />
        </Field>
      </div>
      <ErrorText>{state.error}</ErrorText>
      <button className={`${buttonClass.primary} self-start`} disabled={pending}>
        {pending ? t("common.saving") : t("platform.payout.submit")}
      </button>
    </form>
  );
}
