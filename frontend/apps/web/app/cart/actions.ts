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
export async function addToCart(classId: string, monthId: string | null, couponCode: string | null = null): Promise<CartActionResult> {
  const code = couponCode && CODE.test(couponCode) ? couponCode.toUpperCase() : null;
  if (await getMe()) {
    const res = await api<Cart>("/me/cart/items", {
      method: "POST",
      body: { class_id: classId, ...(monthId ? { class_month_id: monthId } : {}), ...(code ? { coupon_code: code } : {}) },
    });
    if (!res.ok) return { ok: false, error: errorText(t, res.error), code: res.error.code };
  } else {
    const jar = await cookies();
    const items = parseGuestCart(jar.get(CART_COOKIE)?.value);
    const existing = items.find((i) => i.class_id === classId && i.class_month_id === monthId);
    if (existing) {
      if (code) existing.coupon_code = code;
    } else {
      if (items.length >= MAX_GUEST_ITEMS) return { ok: false, error: t("errors.CART_FULL"), code: "CART_FULL" };
      items.push({ class_id: classId, class_month_id: monthId, ...(code ? { coupon_code: code } : {}) });
    }
    jar.set(CART_COOKIE, serializeGuestCart(items), cartCookie());
  }
  revalidatePath("/", "layout");
  return { ok: true };
}

const CODE = /^[A-Za-z0-9-]{4,20}$/;

/** A coupon code for the courses in the cart it is valid for (each code belongs to one teacher's organization).
 * A guest's codes are kept in the cart cookie, only on the items they actually discount. */
export async function applyCoupon(raw: string): Promise<CartActionResult> {
  const code = raw.trim().toUpperCase();
  if (!CODE.test(code)) return { ok: false, error: t("errors.COUPON_INVALID"), code: "COUPON_INVALID" };
  if (await getMe()) {
    const res = await api<Cart>("/me/cart/coupon", { method: "POST", body: { code } });
    if (!res.ok) return { ok: false, error: errorText(t, res.error), code: res.error.code };
  } else {
    const jar = await cookies();
    const items = parseGuestCart(jar.get(CART_COOKIE)?.value);
    const trial = items.map((i) => (i.class_month_id ? i : { ...i, coupon_code: code }));
    const res = await api<Cart>("/market/cart/preview", { method: "POST", body: { items: trial }, token: null });
    if (!res.ok) return { ok: false, error: errorText(t, res.error), code: res.error.code };
    const works = new Set(res.data.items.filter((i) => i.coupon_code === code && !i.coupon_public).map((i) => i.class_id));
    if (works.size === 0) return { ok: false, error: t("errors.COUPON_INVALID"), code: "COUPON_INVALID" };
    jar.set(CART_COOKIE, serializeGuestCart(items.map((i) => (works.has(i.class_id) ? { ...i, coupon_code: code } : i))),
            cartCookie());
  }
  revalidatePath("/cart");
  return { ok: true };
}

export async function removeCoupon(code: string): Promise<void> {
  if (await getMe()) {
    await api(`/me/cart/coupon/${encodeURIComponent(code)}`, { method: "DELETE" });
  } else {
    const jar = await cookies();
    const items = parseGuestCart(jar.get(CART_COOKIE)?.value)
      .map((i) => (i.coupon_code?.toUpperCase() === code.toUpperCase() ? { ...i, coupon_code: null } : i));
    jar.set(CART_COOKIE, serializeGuestCart(items), cartCookie());
  }
  revalidatePath("/cart");
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
