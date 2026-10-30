"use client";

import { useActionState } from "react";

import { ErrorText, Field, Input, Select, buttonClass } from "@eduzone/ui";
import { useT } from "@eduzone/lib/i18n/client";
import type { PlatformTenant } from "@eduzone/lib/types";

import type { ActionState as FormState } from "@eduzone/ui";

const GB = 1024 ** 3;
const gb = (bytes: number | null | undefined) => (bytes == null ? "" : String(Math.round(bytes / GB)));

/** Create an organization (with its owner), or edit one when `initial` is given. */
export function TenantForm({ action, initial }: {
  action: (state: FormState, fd: FormData) => Promise<FormState>;
  initial?: PlatformTenant;
}) {
  const t = useT();
  const [state, submit, pending] = useActionState(action, {});
  return (
    <form action={submit} className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("platform.form.name")}>
          <Input name="name" required minLength={2} maxLength={120} defaultValue={initial?.name} />
        </Field>
        {initial ? (
          <Field label={t("platform.form.status")}>
            <Select name="status" defaultValue={initial.status}>
              {(["active", "pending", "suspended", "closed"] as const).map((s) => (
                <option key={s} value={s}>{t(`platform.status.${s}`)}</option>
              ))}
            </Select>
          </Field>
        ) : (
          <Field label={t("platform.form.slug")} hint={t("platform.form.slugHint")}>
            <Input name="slug" required pattern="[a-z0-9][a-z0-9-]{1,38}[a-z0-9]" maxLength={40} />
          </Field>
        )}
        {!initial && (
          <Field label={t("platform.form.orgType")}>
            <Select name="org_type" defaultValue="individual">
              {(["individual", "institute", "corporate"] as const).map((o) => (
                <option key={o} value={o}>{t(`platform.orgType.${o}`)}</option>
              ))}
            </Select>
          </Field>
        )}
        <Field label={t("platform.form.commission")}>
          <Input name="commission" inputMode="decimal" required
                 defaultValue={initial ? String(initial.commission_bps / 100) : "20"} />
        </Field>
        <Field label={t("platform.form.feeBearerLabel")}>
          <Select name="gateway_fee_bearer" defaultValue={initial?.gateway_fee_bearer ?? "tenant"}>
            <option value="tenant">{t("platform.form.feeBearer.tenant")}</option>
            <option value="platform">{t("platform.form.feeBearer.platform")}</option>
          </Select>
        </Field>
        <Field label={`${t("platform.form.color")} (${t("common.optional")})`}>
          <Input name="primary_color" pattern="#[0-9A-Fa-f]{6}" placeholder="#1E6FD9" defaultValue={initial?.primary_color ?? ""} />
        </Field>
        <Field label={`${t("platform.form.library")} (${t("common.optional")})`}>
          <Input name="bunny_library_id" inputMode="numeric" pattern="[0-9]*" defaultValue={initial?.bunny_library_id ?? ""} />
        </Field>
        <Field label={`${t("platform.form.storageGb")} (${t("common.optional")})`}>
          <Input name="storage_gb" inputMode="numeric" defaultValue={gb(initial?.storage_limit_bytes)} />
        </Field>
        <Field label={`${t("platform.form.bandwidthGb")} (${t("common.optional")})`}>
          <Input name="bandwidth_gb" inputMode="numeric" defaultValue={gb(initial?.bandwidth_limit_bytes)} />
        </Field>
        {initial ? (
          <>
            <Field label={`${t("platform.form.bankName")} (${t("common.optional")})`}>
              <Input name="payout_bank_name" maxLength={100} defaultValue={initial.payout_bank_name ?? ""} />
            </Field>
            <Field label={`${t("platform.form.bankAccount")} (${t("common.optional")})`}>
              <Input name="payout_account_masked" maxLength={30} defaultValue={initial.payout_account_masked ?? ""} />
            </Field>
          </>
        ) : (
          <>
            <Field label={t("platform.form.ownerEmail")} hint={t("platform.form.ownerEmailHint")}>
              <Input name="owner_email" type="email" autoComplete="off" required />
            </Field>
            <Field label={t("platform.form.ownerName")}>
              <Input name="owner_name" required maxLength={120} />
            </Field>
          </>
        )}
      </div>
      <ErrorText>{state.error}</ErrorText>
      <div className="flex items-center gap-3">
        <button className={buttonClass.primary} disabled={pending}>
          {pending ? t("common.saving") : initial ? t("classForm.save") : t("platform.form.create")}
        </button>
        {state.ok && !pending && <span className="text-sm text-success">{t("classForm.saved")}</span>}
      </div>
    </form>
  );
}
