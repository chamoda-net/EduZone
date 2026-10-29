"use client";

import { useActionState } from "react";

import { ErrorText, Field, Input, buttonClass } from "@eduzone/ui";
import { useT } from "@eduzone/lib/i18n/client";

import { adminLogin, requestAdminCode, type LoginState } from "../../actions";

export function AdminLoginForm() {
  const t = useT();
  const [sent, send, sending] = useActionState<LoginState, FormData>(requestAdminCode, {});
  const [login, submit, signingIn] = useActionState<LoginState, FormData>(
    (prev, fd) => adminLogin({ ...prev, phone: sent.phone }, fd),
    {},
  );

  if (!sent.sent) {
    return (
      <form action={send} className="flex flex-col gap-4">
        <Field label={t("auth.phone")}>
          <Input name="phone" type="tel" inputMode="tel" autoComplete="tel" required defaultValue={sent.phone} autoFocus />
        </Field>
        <ErrorText>{sent.error}</ErrorText>
        <button className={buttonClass.primary} disabled={sending}>
          {sending ? t("common.loading") : t("auth.sendCode")}
        </button>
      </form>
    );
  }
  return (
    <form action={submit} className="flex flex-col gap-4">
      <Field label={t("platform.smsCode")}>
        <Input name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required autoFocus />
      </Field>
      <Field label={t("platform.totpCode")}>
        <Input name="totp" inputMode="numeric" autoComplete="off" pattern="[0-9]{6}" maxLength={6} required />
      </Field>
      <ErrorText>{login.error}</ErrorText>
      <button className={buttonClass.primary} disabled={signingIn}>
        {signingIn ? t("common.loading") : t("auth.verify")}
      </button>
    </form>
  );
}
