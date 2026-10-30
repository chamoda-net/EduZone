"use client";

import { useActionState, useEffect, useTransition } from "react";

import { useT } from "@eduzone/lib/i18n/client";
import type { Me } from "@eduzone/lib/types";
import { Button, ErrorText, Field, Input, Select, toast } from "@eduzone/ui";

import { resendEmail, updateProfile } from "../login/actions";

const EXAMS = ["al", "ol", "grade_5", "other"] as const;

export function ProfileForm({ me }: { me: Me }) {
  const t = useT();
  const [state, submit, pending] = useActionState(updateProfile, {});
  useEffect(() => {
    if (state.ok) toast(t("account.saved"));
  }, [state, t]);

  return (
    <form action={submit} className="grid gap-4 sm:grid-cols-2">
      <Field label={t("auth.fullName")} className="sm:col-span-2">
        <Input name="full_name" autoComplete="name" required maxLength={120} defaultValue={me.full_name} />
      </Field>
      <Field label={t("account.exam")} optional={t("common.optional")}>
        <Select name="exam" defaultValue={me.exam ?? ""}>
          <option value="">{t("account.examNone")}</option>
          {EXAMS.map((e) => (
            <option key={e} value={e}>{t(`exam.${e}`)}</option>
          ))}
        </Select>
      </Field>
      <Field label={t("account.examYear")} optional={t("common.optional")}>
        <Input name="exam_year" type="number" inputMode="numeric" min={2000} max={2100} defaultValue={me.exam_year ?? ""} />
      </Field>
      <Field label={t("account.school")} optional={t("common.optional")} className="sm:col-span-2">
        <Input name="school" maxLength={120} autoComplete="organization" defaultValue={me.school ?? ""} />
      </Field>
      <div className="flex flex-col gap-3 sm:col-span-2">
        <ErrorText>{state.error}</ErrorText>
        <Button loading={pending} className="self-start">
          {t("common.save")}
        </Button>
      </div>
    </form>
  );
}

export function ResendEmailButton() {
  const t = useT();
  const [pending, start] = useTransition();
  return (
    <Button
      size="sm"
      variant="secondary"
      loading={pending}
      onClick={() =>
        start(async () => {
          const r = await resendEmail();
          toast(r.ok ? t("account.emailSent") : (r.error ?? t("errors.generic")), r.ok ? "success" : "error");
        })
      }
    >
      {t("account.resendEmail")}
    </Button>
  );
}
