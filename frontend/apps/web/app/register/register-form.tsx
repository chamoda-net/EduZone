"use client";

import Link from "next/link";
import { useActionState, useState, useTransition } from "react";

import { GoogleButton, googleEnabled } from "@/components/google-button";
import { useT } from "@eduzone/lib/i18n/client";
import { Button, ErrorText, Field, Input, PasswordInput, buttonStyles } from "@eduzone/ui";

import { googleSignIn, register, type SignInState } from "../login/actions";
import { Divider } from "../login/login-form";

export function RegisterForm({ next, email }: { next?: string; email?: string }) {
  const t = useT();
  const [state, submit, pending] = useActionState(register, {});
  const [google, setGoogle] = useState<SignInState>({});
  const [googling, startGoogle] = useTransition();
  const [editedAt, setEditedAt] = useState<number>(); // typing a new email hides its error
  const taken = state.errorCode === "EMAIL_TAKEN";
  const showTaken = taken && editedAt !== state.at;

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
        <div className="flex flex-col gap-3">
          <Field label={t("auth.email")} error={showTaken && <span id="register-email-error">{state.error}</span>}>
            <Input name="email" type="email" autoComplete="email" required defaultValue={state.email ?? email}
                   onInput={() => setEditedAt(state.at)} aria-invalid={showTaken || undefined}
                   aria-describedby={showTaken ? "register-email-error" : undefined} />
          </Field>
          {showTaken && (
            <div className="flex flex-wrap gap-2">
              <Link href={next ? `/login?next=${encodeURIComponent(next)}` : "/login"} className={buttonStyles("secondary", "sm")}>
                {t("auth.signInInstead")}
              </Link>
              <Link href="/recover" className={buttonStyles("ghost", "sm")}>{t("auth.resetPassword")}</Link>
            </div>
          )}
        </div>
        <Field label={t("auth.password")} hint={t("register.passwordHint")} htmlFor="register-password">
          <PasswordInput id="register-password" name="password" autoComplete="new-password" required minLength={8} maxLength={128}
                         showLabel={t("auth.showPassword")} hideLabel={t("auth.hidePassword")} />
        </Field>
        {!taken && <ErrorText>{state.error}</ErrorText>}
        <Button size="lg" loading={pending}>
          {t("register.submit")}
        </Button>
        <p className="text-xs leading-relaxed text-subtle">{t("register.next")}</p>
      </form>
    </div>
  );
}
