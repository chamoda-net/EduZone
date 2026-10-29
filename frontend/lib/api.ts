import "server-only";

import { cookies, headers } from "next/headers";

import { ACCESS_COOKIE, PADMIN_ACCESS_COOKIE, isAdminHost } from "./cookies";

export const API_URL = process.env.API_URL ?? "http://localhost:8000";

export type ApiError = { code: string; message: string };
export type ApiResult<T> = { ok: true; status: number; data: T } | { ok: false; status: number; error: ApiError };

type Options = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  /** Defaults to the session's access token; pass null for an anonymous call. */
  token?: string | null;
};

/** The host the user is on (`<slug>.eduzone.lk`). The backend resolves the tenant from it. */
export async function userHost(): Promise<string> {
  const h = await headers();
  return h.get("x-forwarded-host") ?? h.get("host") ?? "";
}

/** Calls the EduZone API from the server. Never throws for HTTP or network errors. */
export async function api<T>(path: string, { method = "GET", body, token }: Options = {}): Promise<ApiResult<T>> {
  const host = await userHost();
  // On the admin host the session is the platform admin's; elsewhere it's the tenant member's.
  const cookieName = isAdminHost(host) ? PADMIN_ACCESS_COOKIE : ACCESS_COOKIE;
  const accessToken = token === undefined ? (await cookies()).get(cookieName)?.value : token;
  const requestHeaders: Record<string, string> = {
    accept: "application/json",
    // fetch() can't override Host, so the user's host travels in X-Forwarded-Host.
    "x-forwarded-host": host,
  };
  if (body !== undefined) requestHeaders["content-type"] = "application/json";
  if (accessToken) requestHeaders.authorization = `Bearer ${accessToken}`;

  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1${path}`, {
      method,
      headers: requestHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    return { ok: false, status: 503, error: { code: "API_UNREACHABLE", message: "The server is not reachable." } };
  }

  if (res.status === 204) return { ok: true, status: 204, data: undefined as T };
  const json: unknown = await res.json().catch(() => null);
  if (res.ok) return { ok: true, status: res.status, data: json as T };
  const error = (json as { error?: ApiError } | null)?.error;
  return { ok: false, status: res.status, error: error ?? { code: `HTTP_${res.status}`, message: res.statusText } };
}
