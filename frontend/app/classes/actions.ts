"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { api } from "@/lib/api";
import { errorText, t } from "@/lib/i18n";
import type { OpenResource } from "@/lib/types";

import type { FormState } from "../org/classes/actions";

export async function joinClass(slug: string): Promise<FormState> {
  const res = await api(`/student/classes/${encodeURIComponent(slug)}/enroll`, { method: "POST" });
  if (res.status === 401) redirect(`/login?next=/classes/${encodeURIComponent(slug)}`);
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath(`/classes/${slug}`);
  return { ok: true };
}

export async function leaveClass(slug: string): Promise<FormState> {
  const res = await api(`/student/classes/${encodeURIComponent(slug)}/enroll`, { method: "DELETE" });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath(`/classes/${slug}`);
  redirect("/my");
}

export async function requestLateMonth(slug: string, monthId: string, _: FormState, fd: FormData): Promise<FormState> {
  const note = String(fd.get("note") ?? "").trim();
  const res = await api(`/student/months/${monthId}/late-request`, { method: "POST", body: { note: note || null } });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath(`/classes/${slug}`);
  return { ok: true, at: Date.now() };
}

export type OpenResult = { ok: true; data: OpenResource } | { ok: false; error: string };

/** Access check + view count happen in the API; this only relays the signed URL. */
export async function openResource(resourceId: string): Promise<OpenResult> {
  const res = await api<OpenResource>(`/student/resources/${resourceId}/open`, { method: "POST" });
  if (!res.ok) return { ok: false, error: errorText(t, res.error) };
  return { ok: true, data: res.data };
}
