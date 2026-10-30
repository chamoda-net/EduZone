"use server";

import { redirect } from "next/navigation";

import { api } from "@/lib/api";
import type { TokenPair } from "@/lib/cookies";
import { clearSession, deviceId, saveSession } from "@/lib/session";
import { errorText, t } from "@eduzone/lib/i18n";
import type { DeviceCheck, LoginResult, Me, OtpRequested, RecoveryStarted } from "@eduzone/lib/types";

// Every identity step: sign in (password or Google, then the SMS code on a new device),
// register, confirm the phone and email, recover, profile, sign out. Inputs are echoed back in
// the state because React resets a form after each action.

/** Only same-site paths, so a crafted ?next= can't send people elsewhere. */
function safeNext(value: FormDataEntryValue | string | null | undefined): string | null {
  const next = typeof value === "string" ? value : "";
  return next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\") ? next : null;
}

function field(form: FormData, name: string): string {
  return String(form.get(name) ?? "").trim();
}

/** Stores the session, then goes where the person was heading. Students without a verified
 * phone go through the phone step first (it's needed to pay). */
async function finish(tokens: TokenPair, next: string | null): Promise<never> {
  await saveSession(tokens);
  const me = await api<Me>("/auth/me", { token: tokens.access_token });
  const staff = me.ok && me.data.workspaces.length > 0;
  if (me.ok && !me.data.phone_verified && !staff) {
    redirect(`/verify-phone?next=${encodeURIComponent(next ?? "/")}`);
  }
  redirect(next ?? (staff ? "/teach" : "/learn"));
}

// --- Sign in ------------------------------------------------------------------------------

export type SignInState = { error?: string; email?: string; check?: DeviceCheck; next?: string; at?: number };

async function afterLogin(
  res: Awaited<ReturnType<typeof api<LoginResult>>>, email: string, next: string | null,
): Promise<SignInState> {
  if (!res.ok) return { error: errorText(t, res.error), email, next: next ?? undefined };
  if (res.data.status === "device_check") {
    return { check: res.data.device_check, email, next: next ?? undefined, at: Date.now() };
  }
  return finish(res.data.tokens, next);
}

export async function signIn(_: SignInState, form: FormData): Promise<SignInState> {
  const email = field(form, "email");
  const next = safeNext(form.get("next"));
  const res = await api<LoginResult>("/auth/login", {
    method: "POST",
    token: null,
    body: { email, password: String(form.get("password") ?? ""), device_id: await deviceId() },
  });
  return afterLogin(res, email, next);
}

export async function googleSignIn(credential: string, nextPath: string | null): Promise<SignInState> {
  const res = await api<LoginResult>("/auth/google", {
    method: "POST",
    token: null,
    body: { id_token: credential, device_id: await deviceId() },
  });
  return afterLogin(res, "", safeNext(nextPath));
}

export type CodeState = { error?: string; code?: string; at?: number };

export async function verifyDevice(_: CodeState, form: FormData): Promise<CodeState> {
  const code = field(form, "code");
  const res = await api<TokenPair>("/auth/device/verify", {
    method: "POST",
    token: null,
    body: { challenge: field(form, "challenge"), code, device_id: await deviceId() },
  });
  if (!res.ok) return { error: errorText(t, res.error), code };
  return finish(res.data, safeNext(form.get("next")));
}

export async function resendDeviceCode(challenge: string): Promise<{ error?: string; resendAfter?: number }> {
  const res = await api<OtpRequested>("/auth/device/resend", { method: "POST", token: null, body: { challenge } });
  return res.ok ? { resendAfter: res.data.resend_after } : { error: errorText(t, res.error) };
}

// --- Register -----------------------------------------------------------------------------

export type RegisterState = { error?: string; name?: string; email?: string };

export async function register(_: RegisterState, form: FormData): Promise<RegisterState> {
  const name = field(form, "full_name");
  const email = field(form, "email");
  const res = await api<TokenPair>("/auth/register", {
    method: "POST",
    token: null,
    body: { full_name: name, email, password: String(form.get("password") ?? ""), device_id: await deviceId() },
  });
  if (!res.ok) return { error: errorText(t, res.error), name, email };
  await saveSession(res.data);
  redirect(`/verify-phone?next=${encodeURIComponent(safeNext(form.get("next")) ?? "/")}`);
}

// --- Phone --------------------------------------------------------------------------------

export type PhoneState = {
  error?: string; errorCode?: string; phone?: string; sent?: boolean; resendAfter?: number; at?: number;
};

export async function requestPhoneCode(_: PhoneState, form: FormData): Promise<PhoneState> {
  const phone = field(form, "phone");
  const res = await api<OtpRequested>("/auth/phone/request", { method: "POST", body: { phone } });
  if (!res.ok) {
    return { error: errorText(t, res.error), errorCode: res.error.code, phone, sent: field(form, "resend") === "1" };
  }
  return { phone, sent: true, resendAfter: res.data.resend_after, at: Date.now() };
}

export async function confirmPhone(_: CodeState, form: FormData): Promise<CodeState> {
  const code = field(form, "code");
  const res = await api("/auth/phone/verify", {
    method: "POST",
    body: { phone: field(form, "phone"), code, device_id: await deviceId() },
  });
  if (!res.ok) return { error: errorText(t, res.error), code };
  const next = safeNext(form.get("next"));
  redirect(next && next !== "/" && next !== "/learn" ? next : "/learn/profile?welcome=1");
}

// --- Email --------------------------------------------------------------------------------

export type SimpleState = { error?: string; ok?: boolean; at?: number };

export async function confirmEmail(_: SimpleState, form: FormData): Promise<SimpleState> {
  const res = await api("/auth/email/verify", { method: "POST", token: null, body: { token: field(form, "token") } });
  return res.ok ? { ok: true, at: Date.now() } : { error: errorText(t, res.error) };
}

export async function resendEmail(): Promise<SimpleState> {
  const res = await api("/auth/email/resend", { method: "POST" });
  return res.ok ? { ok: true, at: Date.now() } : { error: errorText(t, res.error) };
}

// --- Recovery -----------------------------------------------------------------------------

export type RecoveryRequestState = { error?: string; email?: string; sent?: boolean };

export async function requestRecovery(_: RecoveryRequestState, form: FormData): Promise<RecoveryRequestState> {
  const email = field(form, "email");
  const res = await api("/auth/recovery/request", { method: "POST", token: null, body: { email } });
  return res.ok ? { email, sent: true } : { error: errorText(t, res.error), email };
}

export type RecoveryStartState = { error?: string; started?: RecoveryStarted };

export async function startRecovery(token: string): Promise<RecoveryStartState> {
  const res = await api<RecoveryStarted>("/auth/recovery/start", { method: "POST", token: null, body: { token } });
  return res.ok ? { started: res.data } : { error: errorText(t, res.error) };
}

export async function completeRecovery(_: CodeState, form: FormData): Promise<CodeState> {
  const code = field(form, "code");
  const res = await api<TokenPair>("/auth/recovery/complete", {
    method: "POST",
    token: null,
    body: {
      token: field(form, "token"),
      ...(code ? { code } : {}),
      password: String(form.get("password") ?? ""),
      device_id: await deviceId(),
    },
  });
  if (!res.ok) return { error: errorText(t, res.error), code };
  return finish(res.data, null);
}

// --- Profile and sign out -----------------------------------------------------------------

export async function updateProfile(_: SimpleState, form: FormData): Promise<SimpleState> {
  const year = field(form, "exam_year");
  const res = await api("/auth/me", {
    method: "PATCH",
    body: {
      full_name: field(form, "full_name"),
      exam: field(form, "exam") || null,
      exam_year: year ? Number(year) : null,
      school: field(form, "school") || null,
    },
  });
  return res.ok ? { ok: true, at: Date.now() } : { error: errorText(t, res.error) };
}

export async function signOut(): Promise<void> {
  await api("/auth/logout", { method: "POST" });
  await clearSession();
  redirect("/login");
}
