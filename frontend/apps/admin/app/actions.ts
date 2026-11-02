"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { api } from "@/lib/api";
import {
  ACCESS_COOKIE,
  REFRESH_COOKIE,
  accessCookie,
  refreshCookie,
  type TokenPair,
} from "@/lib/cookies";
import { rupeesToCents } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import type { PlatformTenant } from "@eduzone/lib/types";

import type { ActionState as FormState } from "@eduzone/ui";

const text = (fd: FormData, k: string) => String(fd.get(k) ?? "").trim();
const GB = 1024 ** 3;

/** "", or a whole number of GB -> bytes; undefined when it isn't a number. */
function gbToBytes(value: string): number | null | undefined {
  if (!value) return null;
  return /^\d+$/.test(value) ? Number(value) * GB : undefined;
}

// --- sign-in ---------------------------------------------------------------------------

export type LoginState = { sent?: boolean; phone?: string; error?: string };

export async function requestAdminCode(_: LoginState, fd: FormData): Promise<LoginState> {
  const phone = text(fd, "phone");
  const res = await api("/platform/auth/otp/request", { method: "POST", body: { phone }, token: null });
  if (!res.ok) return { phone, error: errorText(t, res.error) };
  return { phone, sent: true };
}

export async function adminLogin(prev: LoginState, fd: FormData): Promise<LoginState> {
  const res = await api<TokenPair>("/platform/auth/login", {
    method: "POST",
    token: null,
    body: { phone: prev.phone, code: text(fd, "code"), totp: text(fd, "totp") },
  });
  if (!res.ok) return { ...prev, error: errorText(t, res.error) };
  const jar = await cookies();
  jar.set(ACCESS_COOKIE, res.data.access_token, accessCookie(res.data.expires_in));
  jar.set(REFRESH_COOKIE, res.data.refresh_token, refreshCookie());
  redirect("/");
}

export async function adminSignOut(): Promise<void> {
  await api("/platform/auth/logout", { method: "POST" });
  const jar = await cookies();
  jar.delete(ACCESS_COOKIE);
  jar.delete(REFRESH_COOKIE);
  redirect("/login");
}

// --- organizations ---------------------------------------------------------------------

function limits(fd: FormData): { storage_limit_bytes: number | null; bandwidth_limit_bytes: number | null } | null {
  const storage = gbToBytes(text(fd, "storage_gb"));
  const bandwidth = gbToBytes(text(fd, "bandwidth_gb"));
  if (storage === undefined || bandwidth === undefined) return null;
  return { storage_limit_bytes: storage, bandwidth_limit_bytes: bandwidth };
}

function commissionBps(fd: FormData): number | null {
  const v = text(fd, "commission");
  return /^\d{1,3}(\.\d{1,2})?$/.test(v) ? Math.round(Number(v) * 100) : null;
}

export async function createTenant(_: FormState, fd: FormData): Promise<FormState> {
  const lim = limits(fd);
  const bps = commissionBps(fd);
  if (!lim || bps === null) return { error: t("platform.form.invalidNumber") };
  const library = text(fd, "bunny_library_id");
  const res = await api<{ tenant: PlatformTenant }>("/platform/tenants", {
    method: "POST",
    body: {
      name: text(fd, "name"),
      slug: text(fd, "slug").toLowerCase(),
      org_type: text(fd, "org_type"),
      commission_bps: bps,
      gateway_fee_bearer: text(fd, "gateway_fee_bearer"),
      primary_color: text(fd, "primary_color") || null,
      bunny_library_id: library ? Number(library) : null,
      ...lim,
      owner_email: text(fd, "owner_email"),
      owner_name: text(fd, "owner_name"),
    },
  });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath("/");
  redirect(`/tenants/${res.data.tenant.id}`);
}

export async function updateTenant(tenantId: string, _: FormState, fd: FormData): Promise<FormState> {
  const lim = limits(fd);
  const bps = commissionBps(fd);
  if (!lim || bps === null) return { error: t("platform.form.invalidNumber") };
  const library = text(fd, "bunny_library_id");
  const res = await api(`/platform/tenants/${tenantId}`, {
    method: "PATCH",
    body: {
      name: text(fd, "name"),
      status: text(fd, "status"),
      commission_bps: bps,
      gateway_fee_bearer: text(fd, "gateway_fee_bearer"),
      primary_color: text(fd, "primary_color") || null,
      bunny_library_id: library ? Number(library) : null,
      payout_bank_name: text(fd, "payout_bank_name") || null,
      payout_account_masked: text(fd, "payout_account_masked") || null,
      ...lim,
    },
  });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath(`/tenants/${tenantId}`);
  revalidatePath("/");
  return { ok: true, at: Date.now() };
}

// --- teacher applications --------------------------------------------------------------

export async function decideApplication(applicationId: string, _: FormState, fd: FormData): Promise<FormState> {
  const res = await api(`/platform/applications/${applicationId}/decision`, {
    method: "POST",
    body: { decision: text(fd, "decision"), note: text(fd, "note") || null },
  });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath(`/applications/${applicationId}`);
  revalidatePath("/applications");
  revalidatePath("/");
  return { ok: true, at: Date.now() };
}

/** The full payout account number; the API audits every reveal. */
export async function revealAccount(applicationId: string): Promise<{ number?: string; error?: string }> {
  const res = await api<{ account_number: string }>(`/platform/applications/${applicationId}/reveal-account`, {
    method: "POST",
  });
  return res.ok ? { number: res.data.account_number } : { error: errorText(t, res.error) };
}

export async function recordPayout(tenantId: string, _: FormState, fd: FormData): Promise<FormState> {
  const amount = rupeesToCents(text(fd, "amount"));
  if (amount === null || amount <= 0) return { error: t("classForm.invalidAmount") };
  const res = await api(`/platform/tenants/${tenantId}/payouts`, {
    method: "POST",
    body: {
      amount_cents: amount,
      period_start: text(fd, "period_start"),
      period_end: text(fd, "period_end"),
      bank_reference: text(fd, "bank_reference"),
    },
  });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath(`/tenants/${tenantId}`);
  return { ok: true, at: Date.now() };
}

// --- phase 8: listing, subjects, users, checkouts ---------------------------------------

export async function setListed(tenantId: string, listed: boolean): Promise<FormState> {
  const res = await api(`/platform/tenants/${tenantId}`, { method: "PATCH", body: { is_listed: listed } });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath(`/tenants/${tenantId}`);
  revalidatePath("/");
  return { ok: true, at: Date.now() };
}

function sortOrder(fd: FormData): number | null {
  const v = text(fd, "sort_order");
  if (!v) return 0;
  return /^\d{1,5}$/.test(v) ? Number(v) : null;
}

export async function createSubject(_: FormState, fd: FormData): Promise<FormState> {
  const order = sortOrder(fd);
  if (order === null) return { error: t("platform.form.invalidNumber") };
  const res = await api("/platform/subjects", {
    method: "POST",
    body: { name: text(fd, "name"), slug: text(fd, "slug").toLowerCase(), sort_order: order },
  });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath("/subjects");
  return { ok: true, at: Date.now() };
}

export async function updateSubject(subjectId: string, _: FormState, fd: FormData): Promise<FormState> {
  const order = sortOrder(fd);
  if (order === null) return { error: t("platform.form.invalidNumber") };
  const res = await api(`/platform/subjects/${subjectId}`, {
    method: "PATCH", body: { name: text(fd, "name"), sort_order: order },
  });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath("/subjects");
  return { ok: true, at: Date.now() };
}

export async function setSubjectActive(subjectId: string, active: boolean): Promise<FormState> {
  const res = await api(`/platform/subjects/${subjectId}`, { method: "PATCH", body: { is_active: active } });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath("/subjects");
  return { ok: true, at: Date.now() };
}

export async function signOutUser(userId: string): Promise<FormState> {
  const res = await api(`/platform/users/${userId}/sign-out`, { method: "POST" });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath(`/users/${userId}`);
  return { ok: true, at: Date.now() };
}

export async function forgetDevice(userId: string, deviceId: string): Promise<FormState> {
  const res = await api(`/platform/users/${userId}/devices/${deviceId}`, { method: "DELETE" });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath(`/users/${userId}`);
  return { ok: true, at: Date.now() };
}

/** Fulfils what is left of a checkout paid at the gateway. Shows the outcome when it doesn't finish. */
export async function retryCheckout(checkoutId: string): Promise<FormState> {
  const res = await api<{ outcome: string }>(`/platform/checkouts/${checkoutId}/retry`, { method: "POST" });
  revalidatePath(`/checkouts/${checkoutId}`);
  revalidatePath("/checkouts");
  if (!res.ok) return { error: errorText(t, res.error) };
  if (res.data.outcome !== "paid") return { error: t("platform.checkouts.retryFailed", { outcome: res.data.outcome }) };
  return { ok: true, at: Date.now() };
}
