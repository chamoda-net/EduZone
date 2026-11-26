"use client";

import { MessageSquareText } from "lucide-react";
import Link from "next/link";
import { useActionState, useEffect, useRef, useState, useTransition } from "react";

import { useCountdown } from "@/components/countdown";
import { GoogleButton, googleEnabled } from "@/components/google-button";
import { useT } from "@eduzone/lib/i18n/client";
import type { DeviceCheck } from "@eduzone/lib/types";
import { Alert, Button, CodeInput, ErrorText, Field, Input, PasswordInput, buttonStyles } from "@eduzone/ui";

import { googleSignIn, resendDeviceCode, signIn, verifyDevice, type SignInState } from "./actions";

/** Which field each failure belongs to. Anything else is shown above the button. */
const WRONG_FIELD: Record<string, "email" | "password"> = {
  LOGIN_EMAIL_UNKNOWN: "email",
  LOGIN_PASSWORD_WRONG: "password",
  LOGIN_NO_PASSWORD: "password",
};

export function LoginForm({ next, email }: { next?: string; email?: string }) {
  const t = useT();
  const [state, submit, pending] = useActionState<SignInState, FormData>(signIn, {});
  const [google, setGoogle] = useState<SignInState>({});
  const [googling, startGoogle] = useTransition();
  const check = google.check ?? state.check;
  const form = useRef<HTMLFormElement>(null);
  const [editedAt, setEditedAt] = useState<number>(); // typing again hides that field's error

  const wrong = state.errorCode ? WRONG_FIELD[state.errorCode] : undefined;
  const shown = editedAt === state.at ? undefined : wrong;
  useEffect(() => {
    if (wrong) form.current?.querySelector<HTMLInputElement>(`input[name=${wrong}]`)?.focus();
  }, [wrong, state.at]);

  if (check) return <DeviceCodeForm check={check} next={next} since={(google.check ? google.at : state.at) ?? 0} />;

  return (
    <div className="flex flex-col gap-5">
      {googleEnabled && (
        <>
          <GoogleButton onCredential={(c) => startGoogle(async () => setGoogle(await googleSignIn(c, next ?? null)))} />
          {googling && <p className="text-center text-sm text-muted">{t("common.loading")}</p>}
          <ErrorText>{google.error}</ErrorText>
          <Divider label={t("auth.or")} />
        </>
      )}
      <form
        ref={form}
        action={submit}
        onInput={(e) => (e.target as HTMLInputElement).name === wrong && setEditedAt(state.at)}
        className="flex flex-col gap-4"
      >
        {next && <input type="hidden" name="next" value={next} />}
        <div className="flex flex-col gap-3">
          <Field label={t("auth.email")} error={shown === "email" && <span id="login-email-error">{state.error}</span>}>
            <Input name="email" type="email" autoComplete="email" required defaultValue={state.email ?? email} autoFocus
                   aria-invalid={shown === "email" || undefined}
                   aria-describedby={shown === "email" ? "login-email-error" : undefined} />
          </Field>
          {shown === "email" && (
            <Link href={next ? `/register?next=${encodeURIComponent(next)}` : "/register"}
                  className={buttonStyles("secondary", "sm", "self-start")}>
              {t("auth.createAccount")}
            </Link>
          )}
        </div>
        <div className="flex flex-col gap-3">
          <Field
            label={t("auth.password")}
            htmlFor="login-password"
            error={shown === "password" && (
              <span id="login-password-error">
                {state.error}
                {state.errorCode === "LOGIN_NO_PASSWORD" && googleEnabled && ` ${t("auth.orGoogle")}`}
              </span>
            )}
          >
            <PasswordInput id="login-password" name="password" autoComplete="current-password" required
                           showLabel={t("auth.showPassword")} hideLabel={t("auth.hidePassword")}
                           aria-invalid={shown === "password" || undefined}
                           aria-describedby={shown === "password" ? "login-password-error" : undefined} />
          </Field>
          {shown === "password" ? (
            <Link href="/recover" className={buttonStyles("secondary", "sm", "self-start")}>
              {t(state.errorCode === "LOGIN_NO_PASSWORD" ? "auth.setPassword" : "auth.resetPassword")}
            </Link>
          ) : (
            <Link href="/recover" className="self-end text-sm font-semibold text-brand hover:underline">
              {t("auth.forgot")}
            </Link>
          )}
        </div>
        {state.errorCode === "LOGIN_RATE_LIMITED" ? (
          <Alert tone="danger">
            <p>{state.error}</p>
            <Link href="/recover" className={buttonStyles("secondary", "sm", "mt-3")}>{t("auth.resetPassword")}</Link>
          </Alert>
        ) : (
          !wrong && <ErrorText>{state.error}</ErrorText>
        )}
        <Button size="lg" loading={pending}>
          {t("auth.verify")}
        </Button>
      </form>
    </div>
  );
}

export function Divider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 text-xs font-semibold tracking-wide text-subtle uppercase">
      <span className="h-px flex-1 bg-border" />
      {label}
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}

/** New device: the code went to the account's phone. Signing in here signs out the other device. */
function DeviceCodeForm({ check, next, since }: { check: DeviceCheck; next?: string; since: number }) {
  const t = useT();
  const [state, submit, pending] = useActionState(verifyDevice, {});
  const [resent, setResent] = useState<{ at: number; after: number; error?: string } | null>(null);
  const [resending, startResend] = useTransition();
  const wait = useCountdown(resent?.after ?? check.resend_after, resent?.at ?? since);

  return (
    <form action={submit} className="flex flex-col gap-4">
      <div className="flex gap-3 rounded-ez bg-brand-50 px-4 py-3 text-sm text-brand-800">
        <MessageSquareText className="mt-0.5 size-4.5 shrink-0" />
        <div>
          <p className="font-semibold">{t("auth.device.title")}</p>
          <p>{t("auth.device.body", { phone: check.phone_hint })}</p>
        </div>
      </div>
      <input type="hidden" name="challenge" value={check.challenge} />
      {next && <input type="hidden" name="next" value={next} />}
      <Field label={t("auth.code")}>
        <CodeInput name="code" defaultValue={state.code} autoFocus />
      </Field>
      <ErrorText>{state.error ?? resent?.error}</ErrorText>
      <Button size="lg" loading={pending}>
        {t("auth.verify")}
      </Button>
      <Button
        type="button"
        variant="link"
        disabled={wait > 0 || resending}
        onClick={() =>
          startResend(async () => {
            const r = await resendDeviceCode(check.challenge);
            setResent({ at: Date.now(), after: r.resendAfter ?? 60, error: r.error });
          })
        }
      >
        {wait > 0 ? t("auth.resendIn", { seconds: wait }) : t("auth.resend")}
      </Button>
      <p className="text-xs text-muted">{t("auth.device.note")}</p>
    </form>
  );
}
