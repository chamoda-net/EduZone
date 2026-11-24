"use client";

import { Send } from "lucide-react";
import { useActionState, useEffect, useRef } from "react";

import { useT } from "@eduzone/lib/i18n/client";
import { Button, Checkbox, ErrorText, Field, Textarea, toast } from "@eduzone/ui";

import type { ActionState as FormState } from "@eduzone/ui";

type Action = (state: FormState, fd: FormData) => Promise<FormState>;

/** The reply composer: starts with a greeting; the sign-off and the quoted message are added by the server. */
export function ReplyForm({ action, email, firstName }: { action: Action; email: string; firstName: string }) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (state.ok) { toast(t("platform.inbox.replySent")); form.current?.reset(); }
  }, [state.ok, state.at, t]);
  return (
    <form ref={form} action={submit} className="flex flex-col gap-3">
      <Field label={t("platform.inbox.reply")} hint={t("platform.inbox.replyHint", { email })}>
        <Textarea name="body" required minLength={2} maxLength={10000} rows={8}
                  defaultValue={`${t("platform.inbox.greeting", { name: firstName })}\n\n`} />
      </Field>
      <Checkbox name="close" label={t("platform.inbox.closeAfter")} />
      <ErrorText>{state.error}</ErrorText>
      <Button loading={pending} icon={<Send className="size-4" />} className="self-start">{t("platform.inbox.send")}</Button>
    </form>
  );
}

export function NoteForm({ action, note }: { action: Action; note: string | null }) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  useEffect(() => { if (state.ok) toast(t("platform.inbox.saved")); }, [state.ok, state.at, t]);
  return (
    <form action={submit} className="flex flex-col gap-3">
      <Field label={t("platform.inbox.notes")} hint={t("platform.inbox.notesHint")}>
        <Textarea name="staff_note" rows={3} maxLength={2000} defaultValue={note ?? ""} />
      </Field>
      <ErrorText>{state.error}</ErrorText>
      <Button variant="secondary" size="sm" loading={pending} className="self-start">{t("platform.inbox.saveNote")}</Button>
    </form>
  );
}

/** Close or reopen. */
export function StatusButton({ action, status, label }: { action: Action; status: string; label: string }) {
  const [state, submit, pending] = useActionState(action, {});
  return (
    <form action={submit}>
      <input type="hidden" name="status" value={status} />
      <Button variant="secondary" size="sm" loading={pending}>{label}</Button>
      {state.error && <p className="mt-1 text-xs text-danger">{state.error}</p>}
    </form>
  );
}
