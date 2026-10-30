// A guest's cart, kept in a cookie until they sign in (then proxy.ts merges it into the account's cart).
// Shared by proxy.ts and server code, so no server-only imports here. It holds only public ids.

const PREFIX = process.env.NODE_ENV === "production" ? "__Host-" : "";
export const CART_COOKIE = `${PREFIX}ez_cart`;
export const MAX_GUEST_ITEMS = 20;

export type GuestItem = { class_id: string; class_month_id: string | null };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

/** Never throws: anything malformed is dropped. */
export function parseGuestCart(value: string | undefined): GuestItem[] {
  if (!value) return [];
  try {
    const raw: unknown = JSON.parse(value);
    if (!Array.isArray(raw)) return [];
    return raw
      .filter((x): x is [string, string | null] =>
        Array.isArray(x) && UUID.test(String(x[0])) && (x[1] === null || UUID.test(String(x[1]))))
      .slice(0, MAX_GUEST_ITEMS)
      .map(([c, m]) => ({ class_id: c, class_month_id: m }));
  } catch {
    return [];
  }
}

export function serializeGuestCart(items: GuestItem[]): string {
  return JSON.stringify(items.slice(0, MAX_GUEST_ITEMS).map((i) => [i.class_id, i.class_month_id]));
}

export const cartCookie = () => ({
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/" as const,
  maxAge: 30 * 24 * 60 * 60,
});
