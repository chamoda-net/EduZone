"use client";

import { useActionState, useState } from "react";

import { ErrorText, Input, buttonClass } from "@eduzone/ui";
import { useT } from "@eduzone/lib/i18n/client";

import type { FormState } from "../../org/classes/actions";

/** "Ask the teacher" for a closed month, with an optional note. */
export function RequestLateForm({ action }: { action: (s: FormState, fd: FormData) => Promise<FormState> }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [state, submit, pending] = useActionState(action, {});

  if (!open) {
    return (
      <button type="button" className={`${buttonClass.secondary} min-h-9 px-3 text-sm`} onClick={() => setOpen(true)}>
        {t("class.requestAccess")}
      </button>
    );
  }
  return (
    <form action={submit} className="flex w-full flex-col gap-2 sm:w-72">
      <Input name="note" maxLength={500} placeholder={t("class.requestNote")} aria-label={t("class.requestNote")} />
      <ErrorText>{state.error}</ErrorText>
      <button className={`${buttonClass.primary} min-h-9 px-3 text-sm`} disabled={pending}>
        {pending ? t("common.saving") : t("class.requestAccess")}
      </button>
    </form>
  );
}
