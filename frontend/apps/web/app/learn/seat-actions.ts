"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { api, type ApiResult } from "@/lib/api";
import { errorText, t } from "@eduzone/lib/i18n";

// Seats in the student area (docs/SEATS.md): ask, withdraw, be told when one opens.

type State = { error?: string; ok?: boolean; at?: number };

function done(classId: string, res: ApiResult<unknown>): State {
  const here = `/learn/classes/${classId}`;
  if (res.status === 401) redirect(`/login?next=${here}`);
  if (!res.ok && res.error.code === "PHONE_NOT_VERIFIED") redirect(`/verify-phone?next=${here}`);
  revalidatePath(here);
  return res.ok ? { ok: true, at: Date.now() } : { error: errorText(t, res.error) };
}

export async function askForSeat(classId: string, monthId: string | null, _: State, fd: FormData): Promise<State> {
  const note = String(fd.get("note") ?? "").trim();
  return done(classId, await api(`/learn/classes/${classId}/seat-request`, {
    method: "POST", body: { class_month_id: monthId, note: note || null },
  }));
}

export async function withdrawSeatRequest(classId: string, monthId: string | null): Promise<State> {
  const month = monthId ? `?class_month_id=${monthId}` : "";
  return done(classId, await api(`/learn/classes/${classId}/seat-request${month}`, { method: "DELETE" }));
}

export async function waitForSeat(classId: string): Promise<State> {
  return done(classId, await api(`/learn/classes/${classId}/seat-wait`, { method: "PUT" }));
}

export async function stopWaiting(classId: string): Promise<State> {
  return done(classId, await api(`/learn/classes/${classId}/seat-wait`, { method: "DELETE" }));
}
