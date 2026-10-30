"use client";

import { CircleCheck } from "lucide-react";
import Link from "next/link";
import { useActionState } from "react";

import { useT } from "@eduzone/lib/i18n/client";
import { Button, ErrorText, buttonStyles } from "@eduzone/ui";

import { confirmEmail } from "../login/actions";

export function ConfirmEmailForm({ token }: { token: string }) {
  const t = useT();
  const [state, submit, pending] = useActionState(confirmEmail, {});

  if (state.ok) {
    return (
      <div className="flex flex-col items-center gap-4 rounded-ez-lg border border-border bg-surface p-6 text-center shadow-ez-sm">
        <span className="grid size-14 place-items-center rounded-full bg-success-bg text-success">
          <CircleCheck className="size-6" />
        </span>
        <p className="font-display text-xl font-semibold">{t("email.done")}</p>
        <Link href="/" className={buttonStyles("primary")}>{t("email.continue")}</Link>
      </div>
    );
  }
  return (
    <form action={submit} className="flex flex-col gap-4">
      <input type="hidden" name="token" value={token} />
      <ErrorText>{state.error}</ErrorText>
      <Button size="lg" loading={pending} disabled={!token}>
        {t("email.confirm")}
      </Button>
    </form>
  );
}
