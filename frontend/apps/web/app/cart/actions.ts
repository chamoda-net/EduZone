"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";

import { api } from "@/lib/api";
import { CART_COOKIE, MAX_GUEST_ITEMS, cartCookie, parseGuestCart, serializeGuestCart } from "@/lib/cart-cookie";
import { getMe } from "@/lib/session";
import { errorText, t } from "@eduzone/lib/i18n";
import type { Cart, CheckoutDetail, CheckoutStarted, GatewayRedirect } from "@eduzone/lib/types";

export type CartActionResult = { ok: true } | { ok: false; error: string; code?: string };

/** Signed in: the account's cart (the API checks it can be bought). Guest: a cookie, priced on the cart page. */
export async function addToCart(classId: string, monthId: string | null): Promise<CartActionResult> {
  if (await getMe()) {
    const res = await api<Cart>("/me/cart/items", {
      method: "POST",
      body: { class_id: classId, ...(monthId ? { class_month_id: monthId } : {}) },
    });
    if (!res.ok) return { ok: false, error: errorText(t, res.error), code: res.error.code };
  } else {
    const jar = await cookies();
    const items = parseGuestCart(jar.get(CART_COOKIE)?.value);
    if (!items.some((i) => i.class_id === classId && i.class_month_id === monthId)) {
      if (items.length >= MAX_GUEST_ITEMS) return { ok: false, error: t("errors.CART_FULL"), code: "CART_FULL" };
      items.push({ class_id: classId, class_month_id: monthId });
      jar.set(CART_COOKIE, serializeGuestCart(items), cartCookie());
    }
  }
  revalidatePath("/", "layout");
  return { ok: true };
}

/** `itemId` for the account's cart; the class and month for a guest's. */
export async function removeFromCart(itemId: string | null, classId: string, monthId: string | null): Promise<void> {
  if (itemId) {
    await api(`/me/cart/items/${itemId}`, { method: "DELETE" });
  } else {
    const jar = await cookies();
    const items = parseGuestCart(jar.get(CART_COOKIE)?.value)
      .filter((i) => !(i.class_id === classId && i.class_month_id === monthId));
    jar.set(CART_COOKIE, serializeGuestCart(items), cartCookie());
  }
  revalidatePath("/", "layout");
}

export type CheckoutResult = { ok: true; redirect: GatewayRedirect } | { ok: false; error: string; code?: string };

/** One checkout for the whole cart; the browser is then sent to the gateway. Access is granted only when the
 * gateway's notification reaches the API, never by coming back to our site. */
export async function startCartCheckout(): Promise<CheckoutResult> {
  const res = await api<CheckoutStarted>("/me/checkouts", { method: "POST" });
  if (res.status === 401) return { ok: false, error: t("errors.UNAUTHORIZED"), code: "UNAUTHORIZED" };
  if (!res.ok) return { ok: false, error: errorText(t, res.error), code: res.error.code };
  return { ok: true, redirect: res.data.redirect };
}

export async function getCheckoutStatus(checkoutId: string): Promise<CheckoutDetail["status"] | null> {
  const res = await api<CheckoutDetail>(`/me/checkouts/${checkoutId}`);
  return res.ok ? res.data.status : null;
}
