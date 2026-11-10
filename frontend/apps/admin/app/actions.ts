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

/** "" = the platform defaults; a percentage -> basis points; undefined when it isn't one. */
function commissionBps(fd: FormData): number | null | undefined {
  const v = text(fd, "commission");
  if (!v) return null;
  return /^\d{1,3}(\.\d{1,2})?$/.test(v) && Number(v) <= 100 ? Math.round(Number(v) * 100) : undefined;
}

export async function createTenant(_: FormState, fd: FormData): Promise<FormState> {
  const lim = limits(fd);
  const bps = commissionBps(fd);
  if (!lim || bps === undefined) return { error: t("platform.form.invalidNumber") };
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
  if (!lim) return { error: t("platform.form.invalidNumber") };
  const library = text(fd, "bunny_library_id");
  const res = await api(`/platform/tenants/${tenantId}`, {
    method: "PATCH",
    body: {
      name: text(fd, "name"),
      status: text(fd, "status"),
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

// --- courses: review queue and categories (docs/COURSES.md, step C1) --------------------

export async function decideCourse(courseId: string, _: FormState, fd: FormData): Promise<FormState> {
  const res = await api(`/platform/courses/${courseId}/decision`, {
    method: "POST", body: { decision: text(fd, "decision"), note: text(fd, "note") || null },
  });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath(`/courses/${courseId}`);
  revalidatePath("/courses");
  return { ok: true, at: Date.now() };
}

export async function unpublishCourse(courseId: string, _: FormState, fd: FormData): Promise<FormState> {
  const res = await api(`/platform/courses/${courseId}/unpublish`, { method: "POST", body: { note: text(fd, "note") } });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath(`/courses/${courseId}`);
  revalidatePath("/courses");
  return { ok: true, at: Date.now() };
}

export async function createCategory(_: FormState, fd: FormData): Promise<FormState> {
  const order = sortOrder(fd);
  if (order === null) return { error: t("platform.form.invalidNumber") };
  const parent = text(fd, "parent_id");
  const res = await api("/platform/course-categories", {
    method: "POST",
    body: {
      slug: text(fd, "slug").toLowerCase(), name_en: text(fd, "name_en"), name_si: text(fd, "name_si") || null,
      name_ta: text(fd, "name_ta") || null, parent_id: parent ? Number(parent) : null, sort_order: order,
    },
  });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath("/course-categories");
  return { ok: true, at: Date.now() };
}

export async function updateCategory(categoryId: number, _: FormState, fd: FormData): Promise<FormState> {
  const order = sortOrder(fd);
  if (order === null) return { error: t("platform.form.invalidNumber") };
  const res = await api(`/platform/course-categories/${categoryId}`, {
    method: "PATCH",
    body: { name_en: text(fd, "name_en"), name_si: text(fd, "name_si") || null, name_ta: text(fd, "name_ta") || null,
            sort_order: order },
  });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath("/course-categories");
  return { ok: true, at: Date.now() };
}

export async function setCategoryActive(categoryId: number, active: boolean): Promise<FormState> {
  const res = await api(`/platform/course-categories/${categoryId}`, { method: "PATCH", body: { is_active: active } });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath("/course-categories");
  return { ok: true, at: Date.now() };
}

// --- course reviews: moderation (step C4) -------------------------------------------------

export async function hideReview(reviewId: string, _: FormState, fd: FormData): Promise<FormState> {
  const res = await api(`/platform/course-reviews/${reviewId}/hide`, { method: "POST", body: { reason: text(fd, "reason") } });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath("/course-reviews");
  return { ok: true, at: Date.now() };
}

export async function showReview(reviewId: string): Promise<FormState> {
  const res = await api(`/platform/course-reviews/${reviewId}/show`, { method: "POST" });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath("/course-reviews");
  return { ok: true, at: Date.now() };
}

// --- refunds (courses step C6) -----------------------------------------------------------

type RefundOut = { status: string; failure_reason: string | null };

function refundOutcome(r: RefundOut): FormState {
  if (r.status === "processed" || r.status === "rejected") return { ok: true, at: Date.now() };
  // Approved, but the gateway didn't refund it (manual or failed): say so; the page shows what to do next.
  return { error: t("platform.refunds.waiting", { reason: r.failure_reason ?? "" }) };
}

export async function decideRefund(refundId: string, _: FormState, fd: FormData): Promise<FormState> {
  const res = await api<RefundOut>(`/platform/refunds/${refundId}/decision`, {
    method: "POST",
    body: { decision: text(fd, "decision"), note: text(fd, "note") || null },
  });
  revalidatePath(`/refunds/${refundId}`);
  revalidatePath("/refunds");
  if (!res.ok) return { error: errorText(t, res.error) };
  return refundOutcome(res.data);
}

export async function retryRefund(refundId: string): Promise<FormState> {
  const res = await api<RefundOut>(`/platform/refunds/${refundId}/retry`, { method: "POST" });
  revalidatePath(`/refunds/${refundId}`);
  revalidatePath("/refunds");
  if (!res.ok) return { error: errorText(t, res.error) };
  return refundOutcome(res.data);
}

export async function markRefundProcessed(refundId: string, _: FormState, fd: FormData): Promise<FormState> {
  const res = await api<RefundOut>(`/platform/refunds/${refundId}/mark-processed`, {
    method: "POST", body: { gateway_refund_ref: text(fd, "gateway_refund_ref") },
  });
  revalidatePath(`/refunds/${refundId}`);
  revalidatePath("/refunds");
  if (!res.ok) return { error: errorText(t, res.error) };
  return { ok: true, at: Date.now() };
}

// --- commission rates and scheduled changes (courses step C7) -------------------------------

export async function scheduleCommissionChange(_: FormState, fd: FormData): Promise<FormState> {
  const pct = text(fd, "new_rate");
  if (!/^\d{1,3}(\.\d{1,2})?$/.test(pct) || Number(pct) > 100) return { error: t("platform.form.invalidNumber") };
  const date = text(fd, "effective_on");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return { error: t("platform.commission.dateRequired") };
  const scope = text(fd, "scope") === "tenant" ? "tenant" : "platform";
  const res = await api("/platform/commission/changes", {
    method: "POST",
    body: {
      scope,
      tenant_id: scope === "tenant" ? text(fd, "tenant_id") || null : null,
      kind: text(fd, "kind"),
      new_bps: Math.round(Number(pct) * 100),
      effective_at: `${date}T00:00:00+05:30`, // the start of that day in Colombo
      reason: text(fd, "reason"),
    },
  });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath("/commission");
  revalidatePath("/");
  return { ok: true, at: Date.now() };
}

export async function cancelCommissionChange(changeId: string): Promise<FormState> {
  const res = await api(`/platform/commission/changes/${changeId}/cancel`, { method: "POST" });
  revalidatePath("/commission");
  if (!res.ok) return { error: errorText(t, res.error) };
  return { ok: true, at: Date.now() };
}
