"use client";

import { useActionState, useState, useTransition } from "react";

import { GoogleButton, googleEnabled } from "@/components/google-button";
import { useT } from "@eduzone/lib/i18n/client";
import { Button, ErrorText, Field, Input, PasswordInput } from "@eduzone/ui";

import { googleSignIn, register, type SignInState } from "../login/actions";
import { Divider } from "../login/login-form";

export function RegisterForm({ next }: { next?: string }) {
  const t = useT();
  const [state, submit, pending] = useActionState(register, {});
  const [google, setGoogle] = useState<SignInState>({});
  const [googling, startGoogle] = useTransition();

  return (
    <div className="flex flex-col gap-5">
      {googleEnabled && (
        <>
          <GoogleButton
            text="signup_with"
            onCredential={(c) => startGoogle(async () => setGoogle(await googleSignIn(c, next ?? null)))}
          />
          {googling && <p className="text-center text-sm text-muted">{t("common.loading")}</p>}
          <ErrorText>{google.error}</ErrorText>
          <Divider label={t("auth.or")} />
        </>
      )}
      <form action={submit} className="flex flex-col gap-4">
        {next && <input type="hidden" name="next" value={next} />}
        <Field label={t("auth.fullName")} hint={t("register.nameHint")}>
          <Input name="full_name" autoComplete="name" required maxLength={120} defaultValue={state.name} autoFocus />
        </Field>
        <Field label={t("auth.email")}>
          <Input name="email" type="email" autoComplete="email" required defaultValue={state.email} />
        </Field>
        <Field label={t("auth.password")} hint={t("register.passwordHint")} htmlFor="register-password">
          <PasswordInput id="register-password" name="password" autoComplete="new-password" required minLength={8} maxLength={128}
                         showLabel={t("auth.showPassword")} hideLabel={t("auth.hidePassword")} />
        </Field>
        <ErrorText>{state.error}</ErrorText>
        <Button size="lg" loading={pending}>
          {t("register.submit")}
        </Button>
        <p className="text-xs leading-relaxed text-subtle">{t("register.next")}</p>
      </form>
    </div>
  );
}
