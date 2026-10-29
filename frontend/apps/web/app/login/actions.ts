"use server";

import { redirect } from "next/navigation";

import { api } from "@/lib/api";
import type { TokenPair } from "@/lib/cookies";
import { errorText, t } from "@eduzone/lib/i18n";
import { clearSession, deviceId, saveSession } from "@/lib/session";
import type { Me } from "@eduzone/lib/types";

export type RequestCodeState = { phone?: string; sent?: boolean; error?: string; at?: number };
// `code` and `fullName` are echoed back because React resets the form after each action.
export type VerifyState = { error?: string; needName?: boolean; code?: string; fullName?: string };

export async function requestCode(_: RequestCodeState, form: FormData): Promise<RequestCodeState> {
  const phone = String(form.get("phone") ?? "").trim();
  const res = await api("/auth/otp/request", { method: "POST", body: { phone }, token: null });
  if (!res.ok) return { phone, error: errorText(t, res.error) };
  return { phone, sent: true, at: Date.now() };
}

/** Only same-site paths, so a crafted ?next= can't send people elsewhere. */
function safeNext(value: FormDataEntryValue | null): string | null {
  const next = typeof value === "string" ? value : "";
  return next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\") ? next : null;
}

export async function verifyCode(_: VerifyState, form: FormData): Promise<VerifyState> {
  const fullName = String(form.get("full_name") ?? "").trim();
  const code = String(form.get("code") ?? "").trim();
  const res = await api<TokenPair>("/auth/otp/verify", {
    method: "POST",
    token: null,
    body: {
      phone: String(form.get("phone") ?? ""),
      code,
      device_id: await deviceId(),
      ...(fullName ? { full_name: fullName } : {}),
    },
  });
  if (!res.ok) {
    // The code isn't spent until the name arrives, so keep it in the field.
    if (res.error.code === "NAME_REQUIRED") return { needName: true, code };
    return { error: errorText(t, res.error), needName: Boolean(fullName), fullName };
  }

  await saveSession(res.data);
  const me = await api<Me>("/auth/me", { token: res.data.access_token });
  const staff = me.ok && me.data.role !== "student";
  redirect(safeNext(form.get("next")) ?? (staff ? "/org/classes" : "/"));
}

export async function signOut(): Promise<void> {
  await api("/auth/logout", { method: "POST" });
  await clearSession();
  redirect("/login");
}
