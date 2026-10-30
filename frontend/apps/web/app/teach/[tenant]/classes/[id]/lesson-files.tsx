"use client";

import { useActionState } from "react";

import { ErrorText, Field, Input, Select, buttonClass } from "@eduzone/ui";
import { useT } from "@eduzone/lib/i18n/client";
import type { LessonType, Media } from "@eduzone/lib/types";

import type { FormState } from "../actions";

/** Attach a video or PDF from the media library to a lesson. */
export function AttachFileForm({
  action,
  media,
  lessonType,
}: {
  action: (state: FormState, form: FormData) => Promise<FormState>;
  media: Media[];
  lessonType: LessonType;
}) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  // Tute lessons take PDFs only; failed uploads can't be attached.
  const choices = media.filter((m) => m.status !== "failed" && (lessonType !== "document" || m.kind === "document"));
  if (choices.length === 0) return <p className="text-xs text-muted">{t("files.noMedia")}</p>;

  return (
    <form key={state.at} action={submit} className="flex flex-col gap-2">
      <div className="grid gap-2 sm:grid-cols-2">
        <Field label={t("files.pick")}>
          <Select name="media_asset_id" required>
            {choices.map((m) => (
              <option key={m.id} value={m.id}>
                {t(`media.kind.${m.kind}`)} · {m.name}
                {m.status !== "ready" ? ` (${t(`media.status.${m.status}`)})` : ""}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={`${t("files.label")} (${t("common.optional")})`}>
          <Input name="title" maxLength={200} />
        </Field>
      </div>
      <label className="flex min-h-11 items-center gap-2 text-sm">
        <input type="checkbox" name="is_downloadable" />
        {t("files.downloadable")}
      </label>
      <ErrorText>{state.error}</ErrorText>
      <button className={`${buttonClass.secondary} min-h-9 self-start px-3 text-sm`} disabled={pending}>
        {pending ? t("common.saving") : t("files.attach")}
      </button>
    </form>
  );
}
