"use client";

import { useActionState, useState } from "react";

import { ErrorText, Field, Input, Select, buttonClass, inputClass } from "@/components/ui";
import { centsToRupeesInput } from "@/lib/format";
import { useT } from "@/lib/i18n/client";
import type { ClassItem, PricingModel } from "@/lib/types";

import type { FormState } from "./actions";

type Props = {
  action: (state: FormState, form: FormData) => Promise<FormState>;
  initial?: ClassItem;
  /** Pricing model can only change on a draft class with no months or lessons. */
  pricingLocked?: boolean;
};

export function ClassForm({ action, initial, pricingLocked = false }: Props) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  const [pricing, setPricing] = useState<PricingModel>(initial?.pricing_model ?? "monthly");
  const fee = pricing === "monthly" ? initial?.monthly_fee_cents : initial?.one_time_price_cents;

  return (
    <form action={submit} className="flex flex-col gap-4">
      <Field label={t("classForm.title")} hint={initial ? undefined : t("classForm.titleHint")}>
        <Input name="title" required maxLength={200} defaultValue={initial?.title} />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("classForm.subject")}>
          <Input name="subject" maxLength={100} defaultValue={initial?.subject ?? ""} />
        </Field>
        <Field label={t("classForm.exam")}>
          <Select name="exam" defaultValue={initial?.exam ?? ""}>
            <option value="">{t("classForm.none")}</option>
            {(["al", "ol", "grade_5", "other"] as const).map((e) => (
              <option key={e} value={e}>{t(`exam.${e}`)}</option>
            ))}
          </Select>
        </Field>
        <Field label={t("classForm.batchYear")}>
          <Input name="batch_year" type="number" min={2000} max={2100} defaultValue={initial?.batch_year ?? ""} />
        </Field>
        <Field label={t("classForm.medium")}>
          <Select name="medium" defaultValue={initial?.medium ?? ""}>
            <option value="">{t("classForm.none")}</option>
            {(["si", "ta", "en"] as const).map((m) => (
              <option key={m} value={m}>{t(`medium.${m}`)}</option>
            ))}
          </Select>
        </Field>
      </div>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1.5 text-sm font-medium">{t("classForm.pricing")}</legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {(["monthly", "one_time", "free"] as const).map((p) => (
            <label
              key={p}
              className={`flex min-h-11 items-center gap-2 rounded-lg border px-3 ${
                pricing === p ? "border-brand" : "border-border"
              } ${pricingLocked && pricing !== p ? "opacity-50" : ""}`}
            >
              <input
                type="radio"
                name="pricing_model"
                value={p}
                checked={pricing === p}
                disabled={pricingLocked && pricing !== p}
                onChange={() => setPricing(p)}
              />
              {t(`pricing.${p}`)}
            </label>
          ))}
        </div>
        {pricingLocked && <p className="text-xs text-muted">{t("classForm.pricingLocked")}</p>}
      </fieldset>

      {pricing !== "free" && (
        <Field label={pricing === "monthly" ? t("classForm.monthlyFee") : t("classForm.oneTimePrice")}>
          <Input
            key={pricing}
            name="fee"
            inputMode="decimal"
            required
            placeholder="2000"
            defaultValue={centsToRupeesInput(fee ?? null)}
          />
        </Field>
      )}

      {pricing === "monthly" && (
        <label className="flex min-h-11 items-center gap-2">
          <input type="checkbox" name="allow_late_months" defaultChecked={initial?.allow_late_months ?? true} />
          {t("classForm.allowLate")}
        </label>
      )}

      <Field label={t("classForm.maxViews")} hint={t("classForm.maxViewsHint")}>
        <Input name="max_video_views" type="number" min={1} max={1000} defaultValue={initial?.max_video_views ?? ""} />
      </Field>

      <Field label={t("classForm.description")}>
        <textarea name="description" rows={4} maxLength={5000} defaultValue={initial?.description ?? ""} className={`${inputClass} py-2`} />
      </Field>

      <ErrorText>{state.error}</ErrorText>
      <div className="flex items-center gap-3">
        <button className={buttonClass.primary} disabled={pending}>
          {pending ? t("common.saving") : initial ? t("classForm.save") : t("classForm.create")}
        </button>
        {state.ok && !pending && <span className="text-sm text-green-700 dark:text-green-400">{t("classForm.saved")}</span>}
      </div>
    </form>
  );
}
