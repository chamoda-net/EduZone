import { NextResponse, type NextRequest } from "next/server";

import { ACCESS_COOKIE, REFRESH_COOKIE, accessCookie, expiresSoon, refreshCookie, type TokenPair } from "./lib/cookies";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

/** Keeps the admin session alive: rotates the tokens shortly before the access token expires
 * (the session itself ends after 12 hours, so admins sign in again at least twice a day). */
export async function proxy(request: NextRequest) {
  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  if (!refresh || (access && !expiresSoon(access))) return NextResponse.next();

  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1/platform/auth/refresh`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.next();
  }
  const response = (() => {
    if (res.ok) return null;
    request.cookies.delete(ACCESS_COOKIE);
    request.cookies.delete(REFRESH_COOKIE);
    const r = NextResponse.next({ request: { headers: request.headers } });
    r.cookies.delete(ACCESS_COOKIE);
    r.cookies.delete(REFRESH_COOKIE);
    return r;
  })();
  if (response) return response;

  const tokens = (await res.json()) as TokenPair;
  request.cookies.set(ACCESS_COOKIE, tokens.access_token);
  request.cookies.set(REFRESH_COOKIE, tokens.refresh_token);
  const next = NextResponse.next({ request: { headers: request.headers } });
  next.cookies.set(ACCESS_COOKIE, tokens.access_token, accessCookie(tokens.expires_in));
  next.cookies.set(REFRESH_COOKIE, tokens.refresh_token, refreshCookie());
  return next;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|webp|ico)$).*)"],
};
