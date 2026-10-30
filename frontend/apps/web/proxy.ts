import { NextResponse, type NextRequest } from "next/server";

import { WORKSPACE_HEADER } from "./lib/workspace-header";

import { CART_COOKIE, parseGuestCart } from "./lib/cart-cookie";
import {
  ACCESS_COOKIE,
  NOTICE_COOKIE,
  REFRESH_COOKIE,
  accessCookie,
  expiresSoon,
  noticeCookie,
  refreshCookie,
  type TokenPair,
} from "./lib/cookies";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

type CookieChange = { name: string; value: string | null; options?: ReturnType<typeof refreshCookie> };

/** Keeps the session alive: when the access token is missing or about to expire and a
 * refresh token exists, rotate them before the page or Server Action runs. The new
 * cookies are set on the response and also on this request, so server code sees them.
 * Once signed in, a guest's cart cookie is merged into the account's cart and dropped.
 * It also tells server code which console workspace a request is for: `/teach/<slug>/...` sets
 * the x-ez-workspace request header (lib/workspace.ts). Any copy sent by the browser is dropped;
 * the API checks membership of that workspace on every call anyway.
 * (The platform admin is a separate app: `apps/admin`.) */
export async function proxy(request: NextRequest) {
  request.headers.delete(WORKSPACE_HEADER);
  const workspace = request.nextUrl.pathname.match(/^\/teach\/([a-z0-9-]+)(?:\/|$)/)?.[1];
  if (workspace) request.headers.set(WORKSPACE_HEADER, workspace);

  const changes = [...(await refreshSession(request)), ...(await mergeGuestCart(request))];
  // Changes go on this request (so server code sees them) and on the response (so the browser keeps them).
  for (const c of changes) {
    if (c.value === null) request.cookies.delete(c.name);
    else request.cookies.set(c.name, c.value);
  }
  const response = NextResponse.next({ request: { headers: request.headers } });
  for (const c of changes) {
    if (c.value === null) response.cookies.delete(c.name);
    else response.cookies.set(c.name, c.value, c.options);
  }
  return response;
}

async function refreshSession(request: NextRequest): Promise<CookieChange[]> {
  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  if (!refresh || (access && !expiresSoon(access))) return [];

  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-forwarded-host": request.headers.get("host") ?? "" },
      body: JSON.stringify({ refresh_token: refresh }),
      cache: "no-store",
    });
  } catch {
    return []; // API down: leave cookies alone and let the page report it
  }

  if (res.ok) {
    const tokens = (await res.json()) as TokenPair;
    // Server code reads the access token straight away; mergeGuestCart below uses it too.
    request.cookies.set(ACCESS_COOKIE, tokens.access_token);
    return [
      { name: ACCESS_COOKIE, value: tokens.access_token, options: accessCookie(tokens.expires_in) },
      { name: REFRESH_COOKIE, value: tokens.refresh_token, options: refreshCookie() },
    ];
  }

  if (res.status === 401) {
    // The session ended (signed in on another device, logout, password reset): drop it. If it
    // was the one-device rule, leave a note so the next page can say why.
    const code = ((await res.json().catch(() => null)) as { error?: { code?: string } } | null)?.error?.code;
    request.cookies.delete(ACCESS_COOKIE);
    const out: CookieChange[] = [{ name: ACCESS_COOKIE, value: null }, { name: REFRESH_COOKIE, value: null }];
    if (code === "SIGNED_IN_ELSEWHERE") out.push({ name: NOTICE_COOKIE, value: "elsewhere", options: noticeCookie() });
    return out;
  }
  return [];
}

async function mergeGuestCart(request: NextRequest): Promise<CookieChange[]> {
  const raw = request.cookies.get(CART_COOKIE)?.value;
  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  if (!raw || !access) return [];
  const items = parseGuestCart(raw);
  if (items.length > 0) {
    try {
      const res = await fetch(`${API_URL}/api/v1/me/cart/merge`, {
        method: "POST",
        headers: { "content-type": "application/json", authorization: `Bearer ${access}` },
        body: JSON.stringify({ items }),
        cache: "no-store",
      });
      if (res.status >= 500) return []; // try again on the next request
    } catch {
      return [];
    }
  }
  return [{ name: CART_COOKIE, value: null }];
}

export const config = {
  // Pages and Server Actions only; skip static assets and the streamed upload route (/teach/<slug>/upload/...).
  matcher: ["/((?!_next/static|_next/image|teach/[^/]+/upload/|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|webp|ico)$).*)"],
};
