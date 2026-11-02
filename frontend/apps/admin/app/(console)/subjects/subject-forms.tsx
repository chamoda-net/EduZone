"use client";

import { useActionState, useEffect, useRef } from "react";

import type { Schema } from "@eduzone/api-client";
import { ActionButton } from "@eduzone/ui/action-button";
import { Badge, Button, ErrorText, Field, Input, cx, toast } from "@eduzone/ui";
import { useT } from "@eduzone/lib/i18n/client";

import { createSubject, setSubjectActive, updateSubject } from "../../actions";

import type { ActionState } from "@eduzone/ui";

type SubjectRow = Schema<"SubjectRow">;

/** A toast once per successful submit. */
function useDoneToast(state: ActionState, message: string) {
  const shown = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (state.ok && state.at !== shown.current) {
      shown.current = state.at;
      toast(message);
    }
  }, [state, message]);
}

export function NewSubjectForm() {
  const t = useT();
  const [state, submit, pending] = useActionState(createSubject, {});
  useDoneToast(state, t("platform.subjects.created"));
  return (
    <form key={state.at} action={submit} className="flex flex-col gap-3">
      <div className="grid gap-3 sm:grid-cols-[2fr_2fr_1fr]">
        <Field label={t("platform.subjects.name")}>
          <Input name="name" required minLength={2} maxLength={60} placeholder="Combined Mathematics" />
        </Field>
        <Field label={t("platform.subjects.slug")} hint={t("platform.subjects.slugHint")}>
          <Input name="slug" required pattern="[a-z0-9]([a-z0-9\-]{0,38}[a-z0-9])?" maxLength={40}
                 autoCapitalize="none" spellCheck={false} placeholder="combined-maths" />
        </Field>
        <Field label={t("platform.subjects.order")} hint={t("platform.subjects.orderHint")}>
          <Input name="sort_order" inputMode="numeric" pattern="\d{1,5}" defaultValue="0" />
        </Field>
      </div>
      <ErrorText>{state.error}</ErrorText>
      <Button className="self-start" loading={pending}>{t("platform.subjects.add")}</Button>
    </form>
  );
}

/** One subject: rename and reorder inline, hide or show. The address is fixed. */
export function SubjectRowForm({ subject: s }: { subject: SubjectRow }) {
  const t = useT();
  const [state, submit, pending] = useActionState(updateSubject.bind(null, s.id), {});
  useDoneToast(state, t("platform.subjects.saved"));
  return (
    <div className={cx("flex flex-col gap-3 p-4 lg:flex-row lg:items-center", !s.is_active && "bg-sunken/40")}>
      <form action={submit} className="flex flex-1 flex-col gap-2 sm:flex-row sm:items-center">
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <label className="sr-only" htmlFor={`name-${s.id}`}>{t("platform.subjects.name")}</label>
          <Input id={`name-${s.id}`} name="name" defaultValue={s.name} required minLength={2} maxLength={60}
                 className={cx("font-semibold", !s.is_active && "text-muted")} />
          <p className="flex flex-wrap items-center gap-2 px-1 text-xs text-muted">
            <span className="font-mono">/{s.slug}</span>
            <span>· {t("platform.subjects.classes", { count: s.classes })}</span>
            {!s.is_active && <Badge tone="neutral">{t("platform.subjects.hidden")}</Badge>}
          </p>
        </div>
        <div className="flex items-center gap-2 self-start sm:self-center">
          <label className="sr-only" htmlFor={`order-${s.id}`}>{t("platform.subjects.order")}</label>
          <div className="w-20">
            <Input id={`order-${s.id}`} name="sort_order" defaultValue={String(s.sort_order)} inputMode="numeric"
                   pattern="\d{1,5}" className="text-center tabular-nums" title={t("platform.subjects.order")} />
          </div>
          <Button variant="secondary" size="sm" loading={pending}>{t("common.save")}</Button>
        </div>
        {state.error && <ErrorText>{state.error}</ErrorText>}
      </form>
      <ActionButton
        small
        variant="ghost"
        action={setSubjectActive.bind(null, s.id, !s.is_active)}
        label={t(s.is_active ? "platform.subjects.hide" : "platform.subjects.show")}
        confirm={s.is_active && s.classes > 0 ? t("platform.subjects.confirmHide") : undefined}
      />
    </div>
  );
}
