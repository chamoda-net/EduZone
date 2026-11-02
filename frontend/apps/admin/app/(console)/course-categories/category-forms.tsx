"use client";

import { useActionState, useEffect, useRef } from "react";

import type { Schema } from "@eduzone/api-client";
import { ActionButton } from "@eduzone/ui/action-button";
import { Badge, Button, ErrorText, Field, Input, Select, cx, toast } from "@eduzone/ui";
import { useT } from "@eduzone/lib/i18n/client";

import { createCategory, setCategoryActive, updateCategory } from "../../actions";

import type { ActionState } from "@eduzone/ui";

type Category = Schema<"CategoryOut">;

function useDoneToast(state: ActionState, message: string) {
  const shown = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (state.ok && state.at !== shown.current) {
      shown.current = state.at;
      toast(message);
    }
  }, [state, message]);
}

export function NewCategoryForm({ parents }: { parents: Category[] }) {
  const t = useT();
  const [state, submit, pending] = useActionState(createCategory, {});
  useDoneToast(state, t("platform.categories.created"));
  return (
    <form key={state.at} action={submit} className="flex flex-col gap-3">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Field label={t("platform.categories.nameEn")}>
          <Input name="name_en" required minLength={2} maxLength={60} placeholder="Cloud Computing" />
        </Field>
        <Field label={t("platform.categories.slug")} hint={t("platform.categories.slugHint")}>
          <Input name="slug" required pattern="[a-z0-9]([a-z0-9\-]{0,38}[a-z0-9])?" maxLength={40}
                 autoCapitalize="none" spellCheck={false} placeholder="cloud-computing" />
        </Field>
        <Field label={t("platform.categories.parent")}>
          <Select name="parent_id" defaultValue="">
            <option value="">{t("platform.categories.topLevel")}</option>
            {parents.map((p) => <option key={p.id} value={p.id}>{p.name_en}</option>)}
          </Select>
        </Field>
        <Field label={t("platform.categories.nameSi")} optional={t("common.optional")}>
          <Input name="name_si" maxLength={60} lang="si" />
        </Field>
        <Field label={t("platform.categories.nameTa")} optional={t("common.optional")}>
          <Input name="name_ta" maxLength={60} lang="ta" />
        </Field>
        <Field label={t("platform.subjects.order")} hint={t("platform.subjects.orderHint")}>
          <Input name="sort_order" inputMode="numeric" pattern="\d{1,5}" defaultValue="0" />
        </Field>
      </div>
      <ErrorText>{state.error}</ErrorText>
      <Button className="self-start" loading={pending}>{t("platform.categories.add")}</Button>
    </form>
  );
}

/** One category: names and order edited inline, hide or show. */
export function CategoryRow({ category: c }: { category: Category }) {
  const t = useT();
  const [state, submit, pending] = useActionState(updateCategory.bind(null, c.id), {});
  useDoneToast(state, t("platform.subjects.saved"));
  return (
    <div className={cx("flex flex-col gap-3 p-4 xl:flex-row xl:items-center", !c.is_active && "opacity-70")}>
      <form action={submit} className="flex flex-1 flex-col gap-2 lg:flex-row lg:items-center">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="grid gap-2 sm:grid-cols-3">
            <Input name="name_en" defaultValue={c.name_en} required minLength={2} maxLength={60}
                   aria-label={t("platform.categories.nameEn")} className="font-semibold" />
            <Input name="name_si" defaultValue={c.name_si ?? ""} maxLength={60} lang="si"
                   aria-label={t("platform.categories.nameSi")} placeholder={t("platform.categories.nameSi")} />
            <Input name="name_ta" defaultValue={c.name_ta ?? ""} maxLength={60} lang="ta"
                   aria-label={t("platform.categories.nameTa")} placeholder={t("platform.categories.nameTa")} />
          </div>
          <p className="flex items-center gap-2 px-1 text-xs text-muted">
            <span className="font-mono">/courses/{c.slug}</span>
            {!c.is_active && <Badge tone="neutral">{t("platform.subjects.hidden")}</Badge>}
          </p>
        </div>
        <div className="flex items-center gap-2 self-start lg:self-center">
          <div className="w-20">
            <Input name="sort_order" defaultValue={String(c.sort_order)} inputMode="numeric" pattern="\d{1,5}"
                   aria-label={t("platform.subjects.order")} className="text-center tabular-nums" />
          </div>
          <Button variant="secondary" size="sm" loading={pending}>{t("common.save")}</Button>
        </div>
        {state.error && <ErrorText>{state.error}</ErrorText>}
      </form>
      <ActionButton small variant="ghost" action={setCategoryActive.bind(null, c.id, !c.is_active)}
                    label={t(c.is_active ? "platform.subjects.hide" : "platform.subjects.show")} />
    </div>
  );
}
