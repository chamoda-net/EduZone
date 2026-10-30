"use client";

import Link from "next/link";
import { useActionState, useState } from "react";

import { useCountdown } from "@/components/countdown";
import { useT } from "@eduzone/lib/i18n/client";
import { Button, CodeInput, ErrorText, Field, Input } from "@eduzone/ui";

import { confirmPhone, requestPhoneCode, type PhoneState } from "../login/actions";

export function PhoneForm({ next }: { next: string }) {
  const t = useT();
  const [sendState, send, sending] = useActionState<PhoneState, FormData>(requestPhoneCode, {});
  const [verifyState, verify, verifying] = useActionState(confirmPhone, {});
  const [editing, setEditing] = useState(false);
  const wait = useCountdown(sendState.resendAfter, sendState.at);
  const onCode = Boolean(sendState.sent) && !editing;

  if (!onCode) {
    return (
      <form action={(fd) => { setEditing(false); send(fd); }} className="flex flex-col gap-4">
        <Field label={t("auth.phone")} hint={t("auth.phoneHint")}>
          <Input name="phone" type="tel" inputMode="tel" autoComplete="tel" required defaultValue={sendState.phone} autoFocus />
        </Field>
        {sendState.error && (
          <ErrorText>
            {sendState.error}
            {sendState.errorCode === "PHONE_IN_USE" && (
              <>
                {" "}
                <Link href="/recover" className="font-semibold underline">{t("phone.recover")}</Link>
              </>
            )}
          </ErrorText>
        )}
        <Button size="lg" loading={sending}>
          {t("auth.sendCode")}
        </Button>
        <p className="text-xs leading-relaxed text-subtle">{t("phone.why")}</p>
      </form>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <form action={verify} className="flex flex-col gap-4">
        <p className="rounded-ez bg-brand-50 px-3 py-2.5 text-sm text-brand-800">{t("auth.codeSentTo", { phone: sendState.phone ?? "" })}</p>
        <input type="hidden" name="phone" value={sendState.phone} />
        <input type="hidden" name="next" value={next} />
        <Field label={t("auth.code")}>
          <CodeInput name="code" defaultValue={verifyState.code} autoFocus />
        </Field>
        <ErrorText>{verifyState.error ?? sendState.error}</ErrorText>
        <Button size="lg" loading={verifying}>
          {t("phone.confirm")}
        </Button>
      </form>
      <div className="flex flex-wrap justify-between gap-2 text-sm">
        <Button type="button" variant="link" onClick={() => setEditing(true)}>
          {t("auth.changeNumber")}
        </Button>
        <form action={send}>
          <input type="hidden" name="phone" value={sendState.phone} />
          <input type="hidden" name="resend" value="1" />
          <Button variant="link" disabled={sending || wait > 0}>
            {wait > 0 ? t("auth.resendIn", { seconds: wait }) : t("auth.resend")}
          </Button>
        </form>
      </div>
    </div>
  );
}
