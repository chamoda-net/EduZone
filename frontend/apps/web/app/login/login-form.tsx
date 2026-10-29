"use client";

import { useActionState, useState } from "react";

import { ErrorText, Field, Input, buttonClass } from "@eduzone/ui";
import { useT } from "@eduzone/lib/i18n/client";

import { requestCode, verifyCode, type RequestCodeState, type VerifyState } from "./actions";

export function LoginForm({ next }: { next?: string }) {
  const t = useT();
  const [sendState, send, sending] = useActionState<RequestCodeState, FormData>(requestCode, {});
  const [verifyState, verify, verifying] = useActionState<VerifyState, FormData>(verifyCode, {});
  // Which step is showing; the server's answer moves us to the code step.
  const [changingNumber, setChangingNumber] = useState(false);
  const onCodeStep = Boolean(sendState.sent) && !changingNumber;

  if (!onCodeStep) {
    return (
      <form action={(fd) => { setChangingNumber(false); send(fd); }} className="flex flex-col gap-4">
        <Field label={t("auth.phone")} hint={t("auth.phoneHint")}>
          <Input
            name="phone"
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            required
            defaultValue={sendState.phone}
            autoFocus
          />
        </Field>
        <ErrorText>{sendState.error}</ErrorText>
        <button className={buttonClass.primary} disabled={sending}>
          {sending ? t("common.loading") : t("auth.sendCode")}
        </button>
      </form>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <form action={verify} className="flex flex-col gap-4">
        <p className="text-sm text-muted">{t("auth.codeSentTo", { phone: sendState.phone ?? "" })}</p>
        <input type="hidden" name="phone" value={sendState.phone} />
        {next && <input type="hidden" name="next" value={next} />}
        <Field label={t("auth.code")}>
          <Input
            name="code"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]{6}"
            maxLength={6}
            required
            defaultValue={verifyState.code}
            autoFocus={!verifyState.needName}
            className="tracking-[0.4em] text-lg"
          />
        </Field>
        {verifyState.needName && (
          <Field label={t("auth.fullName")} hint={t("auth.fullNameHint")}>
            <Input name="full_name" autoComplete="name" required maxLength={120} defaultValue={verifyState.fullName} autoFocus />
          </Field>
        )}
        <ErrorText>{verifyState.error ?? sendState.error}</ErrorText>
        <button className={buttonClass.primary} disabled={verifying}>
          {verifying ? t("common.loading") : t("auth.verify")}
        </button>
      </form>
      <div className="flex flex-wrap justify-between gap-2 text-sm">
        <button type="button" className={buttonClass.link} onClick={() => setChangingNumber(true)}>
          {t("auth.changeNumber")}
        </button>
        <form action={send}>
          <input type="hidden" name="phone" value={sendState.phone} />
          <button className={buttonClass.link} disabled={sending}>
            {t("auth.resend")}
          </button>
        </form>
      </div>
    </div>
  );
}
