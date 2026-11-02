"use client";

import { useActionState, useEffect, useRef } from "react";

import { Button, ErrorText, Field, Textarea, toast } from "@eduzone/ui";
import { useT } from "@eduzone/lib/i18n/client";

import type { ActionState } from "@eduzone/ui";

type Action = (state: ActionState, fd: FormData) => Promise<ActionState>;

function useDone(state: ActionState, message: string) {
  const shown = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (state.ok && state.at !== shown.current) {
      shown.current = state.at;
      toast(message);
    }
  }, [state, message]);
}

/** Approve (publish) or send back with a note. The submit button that was pressed names the decision. */
export function CourseDecision({ action, canApprove }: { action: Action; canApprove: boolean }) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  useDone(state, t("platform.courses.decided"));
  return (
    <form action={submit} className="flex flex-col gap-3"
          onSubmit={(e) => {
            const decision = ((e.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null)?.value;
            if (decision === "approve" && !window.confirm(t("platform.courses.confirmApprove"))) e.preventDefault();
          }}>
      <Field label={t("platform.courses.note")} hint={t("platform.courses.noteHint")}>
        <Textarea name="note" rows={4} maxLength={2000} />
      </Field>
      <ErrorText>{state.error}</ErrorText>
      <div className="flex flex-wrap gap-2">
        <Button name="decision" value="approve" loading={pending} disabled={!canApprove}>{t("platform.courses.approve")}</Button>
        <Button name="decision" value="request_changes" variant="secondary" loading={pending}>
          {t("platform.courses.requestChanges")}
        </Button>
      </div>
    </form>
  );
}

export function UnpublishForm({ action }: { action: Action }) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  useDone(state, t("platform.courses.decided"));
  return (
    <form action={submit} className="flex flex-col gap-3"
          onSubmit={(e) => { if (!window.confirm(t("platform.courses.confirmUnpublish"))) e.preventDefault(); }}>
      <Field label={t("platform.courses.note")}>
        <Textarea name="note" rows={3} required minLength={3} maxLength={2000} />
      </Field>
      <ErrorText>{state.error}</ErrorText>
      <Button variant="danger" className="self-start" loading={pending}>{t("platform.courses.unpublish")}</Button>
    </form>
  );
}
