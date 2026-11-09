"use client";

import { useActionState } from "react";

import { Button, ErrorText, Input } from "@eduzone/ui";
import { useT } from "@eduzone/lib/i18n/client";

import { hideReview } from "../../actions";

export function HideForm({ reviewId }: { reviewId: string }) {
  const t = useT();
  const [state, submit, pending] = useActionState(hideReview.bind(null, reviewId), {});
  return (
    <form action={submit} className="flex flex-col gap-1.5 sm:flex-row sm:items-start">
      <Input name="reason" required minLength={3} maxLength={500} placeholder={t("platform.reviews.reason")}
             aria-label={t("platform.reviews.reason")} className="sm:max-w-md" />
      <Button variant="secondary" size="sm" loading={pending} className="shrink-0">{t("platform.reviews.hide")}</Button>
      <ErrorText>{state.error}</ErrorText>
    </form>
  );
}
