"use client";

import { useActionState, useState } from "react";

import { ErrorText, Field, Input, Select, buttonClass } from "@/components/ui";
import { formatMonth } from "@/lib/format";
import { useT } from "@/lib/i18n/client";
import type { LessonType, Month } from "@/lib/types";

import type { FormState } from "../actions";

type Action = (state: FormState, form: FormData) => Promise<FormState>;

export function AddMonthForm({ action, suggested }: { action: Action; suggested: string }) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  return (
    // A new key after each success resets the inputs.
    <form key={state.at} action={submit} className="flex flex-col gap-3 border-t border-border pt-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label={t("months.month")}>
          <Input name="month" type="month" required defaultValue={suggested} />
        </Field>
        <Field label={`${t("months.feeOverride")} (${t("common.optional")})`} hint={t("months.feeOverrideHint")}>
          <Input name="fee" inputMode="decimal" />
        </Field>
        <Field label={t("months.status")}>
          <Select name="status" defaultValue="open">
            {(["open", "upcoming", "closed"] as const).map((s) => (
              <option key={s} value={s}>{t(`status.${s}`)}</option>
            ))}
          </Select>
        </Field>
      </div>
      <ErrorText>{state.error}</ErrorText>
      <button className={`${buttonClass.secondary} self-start`} disabled={pending}>
        {pending ? t("common.saving") : t("months.add")}
      </button>
    </form>
  );
}

export function AddLessonForm({ action, months, monthly }: { action: Action; months: Month[]; monthly: boolean }) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  const [type, setType] = useState<LessonType>("live");
  const live = type === "live";

  return (
    <form key={state.at} action={submit} className="flex flex-col gap-3 border-t border-border pt-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("lessons.lessonTitle")}>
          <Input name="title" required maxLength={200} />
        </Field>
        <Field label={t("lessons.type")}>
          <Select name="lesson_type" value={type} onChange={(e) => setType(e.target.value as LessonType)}>
            {(["live", "recorded", "document"] as const).map((x) => (
              <option key={x} value={x}>{t(`lessons.type.${x}`)}</option>
            ))}
          </Select>
        </Field>
        {monthly && (
          <Field label={t("lessons.month")}>
            <Select name="class_month_id" required defaultValue={months.find((m) => m.status === "open")?.id ?? months[0]?.id}>
              {months.map((m) => (
                <option key={m.id} value={m.id}>{formatMonth(m.month_start)}</option>
              ))}
            </Select>
          </Field>
        )}
        {live && (
          <>
            <Field label={t("lessons.scheduledAt")}>
              <Input name="scheduled_at" type="datetime-local" required />
            </Field>
            <Field label={t("lessons.duration")}>
              <Input name="duration_minutes" type="number" min={1} max={1440} defaultValue={120} />
            </Field>
            <Field label={`${t("lessons.zoom")} (${t("common.optional")})`}>
              <Input name="zoom_join_url" type="url" placeholder="https://zoom.us/j/…" />
            </Field>
          </>
        )}
      </div>
      {type === "recorded" && <p className="text-xs text-muted">{t("lessons.videoLater")}</p>}
      <div className="flex flex-wrap gap-4">
        <label className="flex min-h-11 items-center gap-2">
          <input type="checkbox" name="is_published" defaultChecked />
          {t("lessons.published")}
        </label>
        <label className="flex min-h-11 items-center gap-2">
          <input type="checkbox" name="is_free_preview" />
          {t("lessons.freePreview")}
        </label>
      </div>
      <ErrorText>{state.error}</ErrorText>
      <button className={`${buttonClass.secondary} self-start`} disabled={pending}>
        {pending ? t("common.saving") : t("lessons.add")}
      </button>
    </form>
  );
}
