"use client";

import { MailCheck, MessageSquareText } from "lucide-react";
import Link from "next/link";
import { useActionState, useState, useTransition } from "react";

import { useT } from "@eduzone/lib/i18n/client";
import { Button, CodeInput, ErrorText, Field, Input, PasswordInput, buttonStyles } from "@eduzone/ui";

import { completeRecovery, requestRecovery, startRecovery, type RecoveryStartState } from "../login/actions";

export function RecoverRequestForm() {
  const t = useT();
  const [state, submit, pending] = useActionState(requestRecovery, {});

  if (state.sent) {
    return (
      <div className="flex flex-col items-center gap-4 rounded-ez-lg border border-border bg-surface p-6 text-center shadow-ez-sm">
        <span className="grid size-14 place-items-center rounded-full bg-brand-50 text-brand">
          <MailCheck className="size-6" />
        </span>
        <p className="font-display text-xl font-semibold">{t("recover.sentTitle")}</p>
        <p className="text-sm text-muted">{t("recover.sentBody", { email: state.email ?? "" })}</p>
      </div>
    );
  }
  return (
    <form action={submit} className="flex flex-col gap-4">
      <Field label={t("auth.email")}>
        <Input name="email" type="email" autoComplete="email" required defaultValue={state.email} autoFocus />
      </Field>
      <ErrorText>{state.error}</ErrorText>
      <Button size="lg" loading={pending}>
        {t("recover.send")}
      </Button>
    </form>
  );
}

export function RecoverCompleteForm({ token }: { token: string }) {
  const t = useT();
  const [start, setStart] = useState<RecoveryStartState | null>(null);
  const [starting, run] = useTransition();
  const [state, submit, pending] = useActionState(completeRecovery, {});

  if (!start?.started) {
    return (
      <div className="flex flex-col gap-4">
        <ErrorText>{start?.error}</ErrorText>
        {start?.error ? (
          <Link href="/recover" className={buttonStyles("primary", "lg")}>{t("recover.again")}</Link>
        ) : (
          <Button size="lg" loading={starting} onClick={() => run(async () => setStart(await startRecovery(token)))}>
            {t("recover.continue")}
          </Button>
        )}
      </div>
    );
  }

  const { needs_code: needsCode, phone_hint: hint } = start.started;
  return (
    <form action={submit} className="flex flex-col gap-4">
      <input type="hidden" name="token" value={token} />
      {needsCode && (
        <>
          <div className="flex gap-3 rounded-ez bg-brand-50 px-4 py-3 text-sm text-brand-800">
            <MessageSquareText className="mt-0.5 size-4.5 shrink-0" />
            <p>{t("recover.codeSent", { phone: hint ?? "" })}</p>
          </div>
          <Field label={t("auth.code")}>
            <CodeInput name="code" defaultValue={state.code} autoFocus />
          </Field>
        </>
      )}
      <Field label={t("recover.newPassword")} hint={t("register.passwordHint")} htmlFor="recover-password">
        <PasswordInput id="recover-password" name="password" autoComplete="new-password" required minLength={8} maxLength={128}
                       autoFocus={!needsCode} showLabel={t("auth.showPassword")} hideLabel={t("auth.hidePassword")} />
      </Field>
      <ErrorText>{state.error}</ErrorText>
      <Button size="lg" loading={pending}>
        {t("recover.save")}
      </Button>
      <p className="text-xs text-muted">{t("recover.note")}</p>
    </form>
  );
}
