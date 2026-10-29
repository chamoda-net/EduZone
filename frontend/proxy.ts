import { NextResponse, type NextRequest } from "next/server";

import {
  ACCESS_COOKIE,
  PADMIN_ACCESS_COOKIE,
  PADMIN_REFRESH_COOKIE,
  REFRESH_COOKIE,
  accessCookie,
  expiresSoon,
  isAdminHost,
  padminRefreshCookie,
  refreshCookie,
  type TokenPair,
} from "./lib/cookies";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

/** Two kinds of site share this app:
 *  - tenant sites (`<slug>.<base>`): everything except /platform;
 *  - the admin host (`admin.<base>`): only /platform (the EduZone staff console).
 * On both, keep the session alive: when the access token is missing or about to expire and a
 * refresh token exists, rotate them before the page or Server Action runs. The new cookies are
 * set on the response and on this request, so server code sees them. */
export async function proxy(request: NextRequest) {
  const host = request.headers.get("host") ?? "";
  const admin = isAdminHost(host);
  const path = request.nextUrl.pathname;

  if (admin && !path.startsWith("/platform")) {
    return NextResponse.redirect(new URL("/platform", request.url));
  }
  if (!admin && path.startsWith("/platform")) {
    return new NextResponse("Not found", { status: 404 });
  }

  const [accessName, refreshName] = admin
    ? [PADMIN_ACCESS_COOKIE, PADMIN_REFRESH_COOKIE]
    : [ACCESS_COOKIE, REFRESH_COOKIE];
  const access = request.cookies.get(accessName)?.value;
  const refresh = request.cookies.get(refreshName)?.value;
  if (!refresh || (access && !expiresSoon(access))) return NextResponse.next();

  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1/${admin ? "platform/auth/refresh" : "auth/refresh"}`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-forwarded-host": host },
      body: JSON.stringify({ refresh_token: refresh }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.next(); // API down: leave cookies alone and let the page report it
  }

  if (res.ok) {
    const tokens = (await res.json()) as TokenPair;
    request.cookies.set(accessName, tokens.access_token);
    request.cookies.set(refreshName, tokens.refresh_token);
    const response = NextResponse.next({ request: { headers: request.headers } });
    response.cookies.set(accessName, tokens.access_token, accessCookie(tokens.expires_in));
    response.cookies.set(refreshName, tokens.refresh_token, admin ? padminRefreshCookie() : refreshCookie());
    return response;
  }

  if (res.status === 401) {
    // Signed out elsewhere (another device, logout, suspension, expiry): drop the dead session.
    request.cookies.delete(accessName);
    request.cookies.delete(refreshName);
    const response = NextResponse.next({ request: { headers: request.headers } });
    response.cookies.delete(accessName);
    response.cookies.delete(refreshName);
    return response;
  }
  return NextResponse.next();
}

export const config = {
  // Pages and Server Actions only; skip static assets and the streamed upload route.
  matcher: ["/((?!_next/static|_next/image|api/upload|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|webp|ico)$).*)"],
};
