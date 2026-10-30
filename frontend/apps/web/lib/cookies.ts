// Session cookies. Shared by proxy.ts and server code, so no server-only imports here.
// Tokens live only in httpOnly cookies: browser JavaScript never sees them.

// In production the names carry the __Host- prefix (FRONTEND.md section 4): the browser then
// insists on Secure, Path=/ and no Domain, so no other site or subdomain can set or read them.
// Local http can't use Secure cookies, so development drops the prefix.
const PREFIX = process.env.NODE_ENV === "production" ? "__Host-" : "";

export const ACCESS_COOKIE = `${PREFIX}ez_session`;
export const REFRESH_COOKIE = `${PREFIX}ez_refresh`;
export const DEVICE_COOKIE = `${PREFIX}ez_device`;
/** Short-lived note that the session ended because the account signed in elsewhere. */
export const NOTICE_COOKIE = `${PREFIX}ez_notice`;

const REFRESH_MAX_AGE = 30 * 24 * 60 * 60; // matches the backend's refresh_token_ttl_days
const DEVICE_MAX_AGE = 5 * 365 * 24 * 60 * 60;

type CookieOptions = {
  httpOnly: true;
  secure: boolean;
  sameSite: "lax";
  path: "/";
  maxAge: number;
};

function base(maxAge: number): CookieOptions {
  return { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge };
}

export const accessCookie = (expiresIn: number) => base(expiresIn);
export const refreshCookie = () => base(REFRESH_MAX_AGE);
export const deviceCookie = () => base(DEVICE_MAX_AGE);
export const noticeCookie = () => base(10 * 60);

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};

/** True when the JWT is unreadable or expires within `skewSeconds`. No signature check:
 * this only decides whether to refresh early; the backend verifies every token. */
export function expiresSoon(token: string, skewSeconds = 30): boolean {
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const { exp } = JSON.parse(atob(payload)) as { exp?: number };
    return typeof exp !== "number" || exp * 1000 - Date.now() < skewSeconds * 1000;
  } catch {
    return true;
  }
}

