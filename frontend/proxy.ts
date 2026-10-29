import { NextResponse, type NextRequest } from "next/server";

import {
  ACCESS_COOKIE,
  REFRESH_COOKIE,
  accessCookie,
  expiresSoon,
  refreshCookie,
  type TokenPair,
} from "./lib/cookies";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

/** Keeps the session alive: when the access token is missing or about to expire and a
 * refresh token exists, rotate them before the page or Server Action runs. The new
 * cookies are set on the response and also on this request, so server code sees them. */
export async function proxy(request: NextRequest) {
  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  if (!refresh || (access && !expiresSoon(access))) return NextResponse.next();

  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-forwarded-host": request.headers.get("host") ?? "" },
      body: JSON.stringify({ refresh_token: refresh }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.next(); // API down: leave cookies alone and let the page report it
  }

  if (res.ok) {
    const tokens = (await res.json()) as TokenPair;
    request.cookies.set(ACCESS_COOKIE, tokens.access_token);
    request.cookies.set(REFRESH_COOKIE, tokens.refresh_token);
    const response = NextResponse.next({ request: { headers: request.headers } });
    response.cookies.set(ACCESS_COOKIE, tokens.access_token, accessCookie(tokens.expires_in));
    response.cookies.set(REFRESH_COOKIE, tokens.refresh_token, refreshCookie());
    return response;
  }

  if (res.status === 401) {
    // Signed out elsewhere (another device, logout, suspension): drop the dead session.
    request.cookies.delete(ACCESS_COOKIE);
    request.cookies.delete(REFRESH_COOKIE);
    const response = NextResponse.next({ request: { headers: request.headers } });
    response.cookies.delete(ACCESS_COOKIE);
    response.cookies.delete(REFRESH_COOKIE);
    return response;
  }
  return NextResponse.next();
}

export const config = {
  // Pages and Server Actions only; skip static assets and the streamed upload route.
  matcher: ["/((?!_next/static|_next/image|api/upload|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|webp|ico)$).*)"],
};
