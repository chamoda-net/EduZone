"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { api } from "@/lib/api";
import { errorText, t } from "@eduzone/lib/i18n";
import type { CheckoutResult, GatewayRedirect, OpenResource, Order, OrderStatus } from "@eduzone/lib/types";

import type { FormState } from "../teach/[tenant]/classes/actions";

// Student actions in /learn. Every call names the class, month, file or order by id; the API
// finds its organization and checks access there.

export async function joinClass(classId: string): Promise<FormState> {
  const res = await api(`/learn/classes/${classId}/enroll`, { method: "POST" });
  if (res.status === 401) redirect(`/login?next=/learn/classes/${classId}`);
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath(`/learn/classes/${classId}`);
  return { ok: true, at: Date.now() };
}

export async function leaveClass(classId: string): Promise<FormState> {
  const res = await api(`/learn/classes/${classId}/enroll`, { method: "DELETE" });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath("/learn/classes");
  redirect("/learn/classes");
}

export async function requestLateMonth(classId: string, monthId: string, _: FormState, fd: FormData): Promise<FormState> {
  const note = String(fd.get("note") ?? "").trim();
  const res = await api(`/learn/months/${monthId}/late-request`, { method: "POST", body: { note: note || null } });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath(`/learn/classes/${classId}`);
  return { ok: true, at: Date.now() };
}

export type OpenResult = { ok: true; data: OpenResource } | { ok: false; error: string };

/** Access check + view count happen in the API; this only relays the signed URL. */
export async function openResource(resourceId: string): Promise<OpenResult> {
  const res = await api<OpenResource>(`/learn/resources/${resourceId}/open`, { method: "POST" });
  if (!res.ok) return { ok: false, error: errorText(t, res.error) };
  return { ok: true, data: res.data };
}

export type StartCheckoutResult = { ok: true; redirect: GatewayRedirect } | { ok: false; error: string; code?: string };

/** Creates the order and payment; the browser is then sent to the gateway. Access is granted
 * only when the gateway's notification reaches the API, never by coming back to our site. */
export async function startCheckout(classId: string, monthId: string | null): Promise<StartCheckoutResult> {
  const res = await api<CheckoutResult>("/learn/checkout", {
    method: "POST",
    body: { class_id: classId, ...(monthId ? { class_month_id: monthId } : {}) },
  });
  if (res.status === 401) return { ok: false, error: t("errors.UNAUTHORIZED") };
  if (!res.ok) return { ok: false, error: errorText(t, res.error), code: res.error.code };
  return { ok: true, redirect: res.data.redirect };
}

export async function getOrderStatus(orderId: string): Promise<OrderStatus | null> {
  const res = await api<Order>(`/learn/orders/${orderId}`);
  return res.ok ? res.data.status : null;
}
