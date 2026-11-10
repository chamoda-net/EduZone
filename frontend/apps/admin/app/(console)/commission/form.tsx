"use client";

import { useActionState, useEffect, useRef, useState } from "react";

import { useT } from "@eduzone/lib/i18n/client";
import { Button, ErrorText, Field, Input, Select, Textarea, cx, toast } from "@eduzone/ui";

import type { ActionState as FormState } from "@eduzone/ui";

type Tenant = { id: string; name: string };

/** A date input value N days from today in Colombo. */
function colomboDate(days: number): string {
  return new Date(Date.now() + days * 86_400_000 + 5.5 * 3_600_000).toISOString().slice(0, 10);
}

/** Schedule a change: platform-wide or one organization, one product, a new rate, a date and a reason. */
export function ScheduleForm({ action, tenants, noticeDays }: {
  action: (state: FormState, fd: FormData) => Promise<FormState>;
  tenants: Tenant[];
  noticeDays: number;
}) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  const [scope, setScope] = useState<"platform" | "tenant">("platform");
  const form = useRef<HTMLFormElement>(null);
  const shown = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (state.ok && state.at !== shown.current) {
      shown.current = state.at;
      toast(t("platform.commission.scheduled"));
      form.current?.reset();
    }
  }, [state, t]);

  return (
    <form ref={form} action={submit} className="flex flex-col gap-4">
      <fieldset className="grid grid-cols-2 gap-1 rounded-ez bg-sunken p-1">
        <legend className="sr-only">{t("platform.commission.scope")}</legend>
        {(["platform", "tenant"] as const).map((k) => (
          <label key={k} className={cx("flex min-h-10 cursor-pointer items-center justify-center rounded-ez text-sm font-semibold transition",
                                       scope === k ? "bg-surface text-foreground shadow-ez-sm" : "text-muted hover:text-foreground")}>
            <input type="radio" name="scope" value={k} checked={scope === k} onChange={() => setScope(k)} className="sr-only" />
            {t(`platform.commission.scopes.${k}`)}
          </label>
        ))}
      </fieldset>
      {scope === "tenant" && (
        <Field label={t("platform.commission.organization")}>
          <Select name="tenant_id" required defaultValue="">
            <option value="" disabled>{t("platform.commission.pickOrganization")}</option>
            {tenants.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </Select>
        </Field>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("platform.commission.product")}>
          <Select name="kind" defaultValue="course">
            <option value="course">{t("platform.commission.kind.course")}</option>
            <option value="tuition">{t("platform.commission.kind.tuition")}</option>
          </Select>
        </Field>
        <Field label={t("platform.commission.newRate")}>
          <div className="relative">
            <Input name="new_rate" required inputMode="decimal" placeholder="20" className="pr-10" />
            <span className="pointer-events-none absolute top-1/2 right-3.5 -translate-y-1/2 text-sm font-semibold text-muted">%</span>
          </div>
        </Field>
      </div>
      <Field label={t("platform.commission.effective")} hint={t("platform.commission.effectiveHint", { days: noticeDays })}>
        <Input type="date" name="effective_on" required min={colomboDate(1)} defaultValue={colomboDate(noticeDays + 1)} />
      </Field>
      <Field label={t("platform.commission.reason")} hint={t("platform.commission.reasonHint")}>
        <Textarea name="reason" required minLength={3} maxLength={1000} rows={3} />
      </Field>
      <ErrorText>{state.error}</ErrorText>
      <Button type="submit" loading={pending} className="self-start">{t("platform.commission.schedule")}</Button>
    </form>
  );
}
