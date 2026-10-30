"use client";

import { MessageSquareText } from "lucide-react";
import { useActionState, useState } from "react";

import { useT } from "@eduzone/lib/i18n/client";
import { Button, ErrorText, Input } from "@eduzone/ui";

import type { FormState } from "@/app/teach/[tenant]/classes/actions";

/** "Ask the teacher" for a closed month, with an optional note. */
export function RequestLateForm({ action }: { action: (s: FormState, fd: FormData) => Promise<FormState> }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [state, submit, pending] = useActionState(action, {});

  if (!open) {
    return (
      <Button type="button" variant="outline" size="sm" icon={<MessageSquareText className="size-4" />} onClick={() => setOpen(true)}>
        {t("class.requestAccess")}
      </Button>
    );
  }
  return (
    <form action={submit} className="flex w-full flex-col gap-2 sm:w-72">
      <Input name="note" maxLength={500} placeholder={t("class.requestNote")} aria-label={t("class.requestNote")} autoFocus />
      <ErrorText>{state.error}</ErrorText>
      <Button size="sm" loading={pending}>
        {t("class.requestAccess")}
      </Button>
    </form>
  );
}
