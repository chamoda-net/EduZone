import "server-only";

import { cookies } from "next/headers";
import { cache } from "react";

import { api } from "./api";
import {
  ACCESS_COOKIE,
  DEVICE_COOKIE,
  NOTICE_COOKIE,
  REFRESH_COOKIE,
  accessCookie,
  deviceCookie,
  refreshCookie,
  type TokenPair,
} from "./cookies";
import type { Branding, Me } from "@eduzone/lib/types";

/** The current tenant's branding, or null when the host isn't a known, active tenant.
 * Cached per request, so the layout and pages share one API call. */
export const getBranding = cache(async (): Promise<Branding | null> => {
  const res = await api<Branding>("/public/tenant", { token: null });
  return res.ok ? res.data : null;
});

type SessionState = { me: Me | null; endedElsewhere: boolean };

/** The signed-in account (with its membership here), and whether a session just ended because
 * the account signed in on another device. Cached per request. */
export const getSession = cache(async (): Promise<SessionState> => {
  const jar = await cookies();
  const notice = jar.get(NOTICE_COOKIE)?.value === "elsewhere";
  if (!jar.get(ACCESS_COOKIE)) return { me: null, endedElsewhere: notice };
  const res = await api<Me>("/auth/me");
  if (res.ok) return { me: res.data, endedElsewhere: false };
  return { me: null, endedElsewhere: notice || res.error.code === "SIGNED_IN_ELSEWHERE" };
});

export const getMe = cache(async (): Promise<Me | null> => (await getSession()).me);

/** Staff of at least one organization (has a console under /teach). */
export function isStaff(me: Me | null): boolean {
  return me !== null && me.workspaces.length > 0;
}

// Writing cookies is only allowed in Server Actions and Route Handlers.

export async function saveSession(tokens: TokenPair): Promise<void> {
  const jar = await cookies();
  jar.set(ACCESS_COOKIE, tokens.access_token, accessCookie(tokens.expires_in));
  jar.set(REFRESH_COOKIE, tokens.refresh_token, refreshCookie());
}

export async function clearSession(): Promise<void> {
  const jar = await cookies();
  jar.delete(ACCESS_COOKIE);
  jar.delete(REFRESH_COOKIE);
  jar.delete(NOTICE_COOKIE);
}

/** Stable per-browser id for the backend's one-device rule. */
export async function deviceId(): Promise<string> {
  const jar = await cookies();
  const existing = jar.get(DEVICE_COOKIE)?.value;
  if (existing) return existing;
  const id = `web-${crypto.randomUUID()}`;
  jar.set(DEVICE_COOKIE, id, deviceCookie());
  return id;
}
