"use client";

import { useActionState, useState } from "react";

import { ErrorText, Field, Input, Select, buttonClass } from "@eduzone/ui";
import { formatMonth, isoToColomboLocal } from "@eduzone/lib/format";
import { useT } from "@eduzone/lib/i18n/client";
import type { Lesson, LessonType, Month } from "@eduzone/lib/types";

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

/** Add a lesson, or edit one when `initial` is given (visibility is toggled separately). */
export function LessonForm({
  action,
  months,
  monthly,
  initial,
}: {
  action: Action;
  months: Month[];
  monthly: boolean;
  initial?: Lesson;
}) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  const [type, setType] = useState<LessonType>(initial?.lesson_type ?? "live");
  const live = type === "live";
  const defaultMonth = initial?.class_month_id ?? months.find((m) => m.status === "open")?.id ?? months[0]?.id;

  return (
    // A new key after each successful add resets the inputs.
    <form
      key={initial ? undefined : state.at}
      action={submit}
      className={`flex flex-col gap-3 ${initial ? "" : "border-t border-border pt-4"}`}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("lessons.lessonTitle")}>
          <Input name="title" required maxLength={200} defaultValue={initial?.title} />
        </Field>
        <Field label={t("lessons.typeLabel")}>
          <Select name="lesson_type" value={type} onChange={(e) => setType(e.target.value as LessonType)}>
            {(["live", "recorded", "document"] as const).map((x) => (
              <option key={x} value={x}>{t(`lessons.type.${x}`)}</option>
            ))}
          </Select>
        </Field>
        {monthly && (
          <Field label={t("lessons.month")}>
            <Select name="class_month_id" required defaultValue={defaultMonth}>
              {months.map((m) => (
                <option key={m.id} value={m.id}>{formatMonth(m.month_start)}</option>
              ))}
            </Select>
          </Field>
        )}
        {live && (
          <>
            <Field label={t("lessons.scheduledAt")}>
              <Input
                name="scheduled_at"
                type="datetime-local"
                required
                defaultValue={initial?.scheduled_at ? isoToColomboLocal(initial.scheduled_at) : undefined}
              />
            </Field>
            <Field label={t("lessons.duration")}>
              <Input name="duration_minutes" type="number" min={1} max={1440} defaultValue={initial?.duration_minutes ?? 120} />
            </Field>
            <Field label={`${t("lessons.zoom")} (${t("common.optional")})`}>
              <Input name="zoom_join_url" type="url" placeholder="https://zoom.us/j/…" defaultValue={initial?.zoom_join_url ?? ""} />
            </Field>
          </>
        )}
      </div>
      <div className="flex flex-wrap gap-4">
        {!initial && (
          <label className="flex min-h-11 items-center gap-2">
            <input type="checkbox" name="is_published" defaultChecked />
            {t("lessons.published")}
          </label>
        )}
        <label className="flex min-h-11 items-center gap-2">
          <input type="checkbox" name="is_free_preview" defaultChecked={initial?.is_free_preview} />
          {t("lessons.freePreview")}
        </label>
      </div>
      <ErrorText>{state.error}</ErrorText>
      <div className="flex items-center gap-3">
        <button className={`${buttonClass.secondary} self-start`} disabled={pending}>
          {pending ? t("common.saving") : initial ? t("classForm.save") : t("lessons.add")}
        </button>
        {initial && state.ok && !pending && (
          <span className="text-sm text-success">{t("classForm.saved")}</span>
        )}
      </div>
    </form>
  );
}
