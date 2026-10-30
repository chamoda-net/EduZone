"use client";

import { useActionState, useEffect } from "react";

import { useT } from "@eduzone/lib/i18n/client";
import type { TeacherProfile } from "@eduzone/lib/types";
import { Button, ErrorText, Field, Input, Textarea, toast } from "@eduzone/ui";

import { saveProfile } from "./actions";

export function ProfileForm({ profile, origin }: { profile: TeacherProfile; origin: string }) {
  const t = useT();
  const [state, submit, pending] = useActionState(saveProfile, {});
  useEffect(() => {
    if (state.ok) toast(t("profile.saved"));
  }, [state, t]);

  return (
    <form action={submit} className="grid gap-5 sm:grid-cols-2">
      <Field label={t("profile.name")} className="sm:col-span-2">
        <Input name="display_name" required maxLength={80} defaultValue={profile.display_name} />
      </Field>
      <Field label={t("profile.link")} hint={t("profile.linkHint", { example: `${origin}/physics/${profile.slug}` })} className="sm:col-span-2">
        <Input name="slug" required minLength={3} maxLength={40} pattern="[a-z0-9][a-z0-9-]*[a-z0-9]" defaultValue={profile.slug} />
      </Field>
      <Field label={t("profile.headline")} hint={t("profile.headlineHint")} className="sm:col-span-2">
        <Input name="headline" maxLength={120} defaultValue={profile.headline ?? ""} />
      </Field>
      <Field label={t("profile.bio")} className="sm:col-span-2">
        <Textarea name="bio" rows={5} maxLength={2000} defaultValue={profile.bio ?? ""} />
      </Field>
      <Field label={t("profile.highlights")} hint={t("profile.highlightsHint")} className="sm:col-span-2">
        <Textarea name="highlights" rows={4} defaultValue={profile.highlights.join("\n")} />
      </Field>
      <Field label={t("profile.photo")} hint={t("profile.photoHint")} optional={t("common.optional")} className="sm:col-span-2">
        <Input name="photo_url" type="url" defaultValue={profile.photo_url ?? ""} placeholder="https://" />
      </Field>
      <div className="flex flex-col gap-3 sm:col-span-2">
        <ErrorText>{state.error}</ErrorText>
        <Button loading={pending} className="self-start">{t("common.save")}</Button>
      </div>
    </form>
  );
}
