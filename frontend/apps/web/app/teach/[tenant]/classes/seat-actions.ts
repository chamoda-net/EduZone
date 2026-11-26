"use server";

import { revalidatePath } from "next/cache";

import { api } from "@/lib/api";
import { teachHref } from "@/lib/workspace";
import { errorText, t } from "@eduzone/lib/i18n";

// Seats in the console (docs/SEATS.md). The API holds every rule; these shape requests and errors.

/** `code` lets a form offer "go over the limit" after CLASS_FULL. */
export type SeatFormState = { error?: string; code?: string; ok?: boolean; at?: number };

const text = (fd: FormData, name: string) => String(fd.get(name) ?? "").trim();

/** The end of a day (YYYY-MM-DD) in Sri Lanka: midnight of the next one. */
function endOfDay(date: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;
  const next = new Date(`${date}T00:00:00+05:30`);
  return Number.isNaN(next.getTime()) ? null : new Date(next.getTime() + 24 * 3600_000).toISOString();
}

async function send(classId: string, path: string, method: "PUT" | "PATCH" | "DELETE" | "POST", body?: unknown): Promise<SeatFormState> {
  const res = await api(path, { method, body });
  if (!res.ok) return { error: errorText(t, res.error), code: res.error.code };
  revalidatePath(await teachHref(`/classes/${classId}`));
  return { ok: true, at: Date.now() };
}

export async function saveSeatSettings(classId: string, _: SeatFormState, fd: FormData): Promise<SeatFormState> {
  const limit = text(fd, "seat_limit");
  if (limit && !/^[1-9]\d{0,4}$/.test(limit)) return { error: t("seats.limitHint") };
  const starts = text(fd, "starts_on") || null;
  return send(classId, `~/classes/${classId}`, "PATCH", {
    seat_limit: limit ? Number(limit) : null,
    registration: text(fd, "registration"),
    show_seat_count: fd.get("show_seat_count") === "on",
    starts_on: starts,
    registration_after_start: starts ? text(fd, "registration_after_start") || null : null,
    ...(fd.has("renewal_day") ? { renewal_day: Number(text(fd, "renewal_day")) } : {}),
  });
}

export async function saveRenewUntil(classId: string, monthId: string, _: SeatFormState, fd: FormData): Promise<SeatFormState> {
  return send(classId, `~/months/${monthId}`, "PATCH", { renew_until: endOfDay(text(fd, "renew_until")) });
}

export async function keepSeat(classId: string, monthId: string, memberId: string, _: SeatFormState, fd: FormData): Promise<SeatFormState> {
  return send(classId, `~/months/${monthId}/seat-keeps/${memberId}`, "PUT", {
    action: "keep",
    keep_until: endOfDay(text(fd, "keep_until")),
    allow_over_limit: fd.get("allow_over_limit") === "on",
  });
}

export async function releaseSeat(classId: string, monthId: string, memberId: string): Promise<SeatFormState> {
  return send(classId, `~/months/${monthId}/seat-keeps/${memberId}`, "PUT", { action: "release" });
}

/** Give access, on purpose over the limit when `over`. */
export async function grantSeat(
  classId: string, memberId: string, monthId: string | null, source: "manual" | "scholarship", over: boolean,
): Promise<SeatFormState> {
  return send(classId, `~/classes/${classId}/grants`, "POST",
              { student_member_id: memberId, class_month_id: monthId, source, allow_over_limit: over });
}

export async function decideSeatRequest(requestId: string, decision: "approve" | "reject", _: SeatFormState, fd: FormData): Promise<SeatFormState> {
  const res = await api(`~/seat-requests/${requestId}/decision`, {
    method: "POST", body: { decision, note: text(fd, "note") || null },
  });
  if (!res.ok) return { error: errorText(t, res.error), code: res.error.code };
  revalidatePath(await teachHref("/requests"));
  return { ok: true, at: Date.now() };
}
