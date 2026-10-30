import "server-only";

import { cookies } from "next/headers";
import { cache } from "react";

import { api } from "@/lib/api";
import { CART_COOKIE, parseGuestCart } from "@/lib/cart-cookie";
import { getMe } from "@/lib/session";
import type { Cart } from "@eduzone/lib/types";

const EMPTY: Cart = { items: [], total_cents: 0, currency: "LKR", ready: false };

/** The cart of this request: the account's when signed in, else the guest cookie priced from public data. */
export const getCart = cache(async (): Promise<Cart> => {
  if (await getMe()) {
    const res = await api<Cart>("/me/cart");
    return res.ok ? res.data : EMPTY;
  }
  const items = parseGuestCart((await cookies()).get(CART_COOKIE)?.value);
  if (items.length === 0) return EMPTY;
  const res = await api<Cart>("/market/cart/preview", { method: "POST", body: { items }, token: null });
  return res.ok ? res.data : EMPTY;
});

/** How many items, for the header badge (no pricing calls). */
export async function cartCount(): Promise<number> {
  const me = await getMe();
  if (me) return me.cart_count;
  return parseGuestCart((await cookies()).get(CART_COOKIE)?.value).length;
}

/** "Is this month (or one-time class) already in the cart?" */
export function inCart(cart: Cart, classId: string, monthId: string | null): boolean {
  return cart.items.some((i) => i.class_id === classId && i.class_month_id === monthId);
}
