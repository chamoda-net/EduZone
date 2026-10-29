// Platform admin session cookies. Shared by proxy.ts and server code (no server-only imports).
// Tokens live only in httpOnly cookies: browser JavaScript never sees them.

export const ACCESS_COOKIE = "ez_padmin_access";
export const REFRESH_COOKIE = "ez_padmin_refresh";
const SESSION_MAX_AGE = 12 * 60 * 60; // matches the backend's platform_session_hours

export type TokenPair = { access_token: string; refresh_token: string; token_type: string; expires_in: number };

function base(maxAge: number) {
  return { httpOnly: true as const, secure: process.env.NODE_ENV === "production", sameSite: "strict" as const, path: "/" as const, maxAge };
}

export const accessCookie = (expiresIn: number) => base(expiresIn);
export const refreshCookie = () => base(SESSION_MAX_AGE);

/** True when the JWT is unreadable or expires within `skewSeconds` (no signature check: the API verifies). */
export function expiresSoon(token: string, skewSeconds = 30): boolean {
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const { exp } = JSON.parse(atob(payload)) as { exp?: number };
    return typeof exp !== "number" || exp * 1000 - Date.now() < skewSeconds * 1000;
  } catch {
    return true;
  }
}
