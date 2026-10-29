import "server-only";

import { cookies } from "next/headers";

import { ACCESS_COOKIE } from "./cookies";

// The admin app runs on the private network and talks to the API's /platform routes.
export const API_URL = process.env.API_URL ?? "http://localhost:8000";

export type ApiError = { code: string; message: string };
export type ApiResult<T> = { ok: true; status: number; data: T } | { ok: false; status: number; error: ApiError };

type Options = { method?: "GET" | "POST" | "PATCH" | "DELETE"; body?: unknown; token?: string | null };

/** Calls the EduZone API from the admin server. Never throws for HTTP or network errors. */
export async function api<T>(path: string, { method = "GET", body, token }: Options = {}): Promise<ApiResult<T>> {
  const accessToken = token === undefined ? (await cookies()).get(ACCESS_COOKIE)?.value : token;
  const headers: Record<string, string> = { accept: "application/json" };
  if (body !== undefined) headers["content-type"] = "application/json";
  if (accessToken) headers.authorization = `Bearer ${accessToken}`;
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1${path}`, {
      method, headers, body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store",
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
