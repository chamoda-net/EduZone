import "server-only";

import { cookies } from "next/headers";
import { cache } from "react";

import { api } from "./api";
import {
  ACCESS_COOKIE,
  DEVICE_COOKIE,
  REFRESH_COOKIE,
  accessCookie,
  deviceCookie,
  refreshCookie,
  type TokenPair,
} from "./cookies";
import type { Branding, Me } from "./types";

/** The current tenant's branding, or null when the host isn't a known, active tenant.
 * Cached per request, so the layout and pages share one API call. */
export const getBranding = cache(async (): Promise<Branding | null> => {
  const res = await api<Branding>("/public/tenant", { token: null });
  return res.ok ? res.data : null;
});

/** The signed-in member of this tenant, or null. */
export const getMe = cache(async (): Promise<Me | null> => {
  if (!(await cookies()).get(ACCESS_COOKIE)) return null;
  const res = await api<Me>("/auth/me");
  return res.ok ? res.data : null;
});

export function isStaff(me: Me | null): boolean {
  return me !== null && me.role !== "student";
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
