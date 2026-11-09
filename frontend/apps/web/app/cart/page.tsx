import { AlertTriangle, CalendarDays, Compass, ShieldCheck, ShoppingCart, Tag, Trash2 } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { SiteShell } from "@/components/shell";
import { TeacherAvatar } from "@/components/teacher-avatar";
import { getCart } from "@/lib/cart";
import { getMe } from "@/lib/session";
import { formatMoney, formatMonth } from "@eduzone/lib/format";
import { t } from "@eduzone/lib/i18n";
import type { CartItem } from "@eduzone/lib/types";
import { Alert, ClassCover, EmptyState, buttonStyles, cx } from "@eduzone/ui";

import { removeFromCart } from "./actions";
import { CheckoutButton } from "./checkout-button";
import { CouponForm } from "./coupon-form";

export const metadata: Metadata = { title: "Cart | EduZone", robots: { index: false } };

const KNOWN_PROBLEMS = ["ALREADY_HAS_ACCESS", "LATE_APPROVAL_REQUIRED", "MONTH_NOT_OPEN", "UNAVAILABLE", "FREE_CLASS"] as const;
type KnownProblem = (typeof KNOWN_PROBLEMS)[number];
const isKnown = (code: string): code is KnownProblem => (KNOWN_PROBLEMS as readonly string[]).includes(code);

/** /cart: months and courses from any teacher, paid together. Grouped by who receives the money. */
export default async function CartPage() {
  const [cart, me] = await Promise.all([getCart(), getMe()]);
  const groups = new Map<string, CartItem[]>();
  for (const item of cart.items) {
    const key = item.org.slug || "unavailable";
    groups.set(key, [...(groups.get(key) ?? []), item]);
  }
  const problems = cart.items.some((i) => i.problem);
  const hasCourses = cart.items.some((i) => i.path.startsWith("/course/"));
  const free = cart.ready && cart.total_cents === 0;

  return (
    <SiteShell>
      <header className="ez-rise flex flex-col gap-2">
        <p className="text-xs font-bold tracking-[0.14em] text-brand-600 uppercase">{t("cart.eyebrow")}</p>
        <h1 className="font-display text-4xl font-semibold sm:text-5xl">{t("cart.title")}</h1>
        {cart.items.length > 0 && <p className="text-muted">{t("cart.lead")}</p>}
      </header>

      {cart.items.length === 0 ? (
        <EmptyState
          icon={<ShoppingCart />}
          title={t("cart.empty.title")}
          body={t("cart.empty.body")}
          action={
            <Link href="/classes" className={buttonStyles("primary")}>
              <Compass className="size-4.5" />
              {t("cart.empty.browse")}
            </Link>
          }
        />
      ) : (
        <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="flex min-w-0 flex-col gap-6">
            {problems && <Alert tone="warning">{t("cart.fixFirst")}</Alert>}
            {[...groups.entries()].map(([key, items], g) => (
              <section key={key} className="ez-rise flex flex-col gap-3" style={{ "--i": g } as React.CSSProperties}>
                {items[0].org.name && (
                  <h2 className="text-xs font-bold tracking-[0.12em] text-muted uppercase">{items[0].org.name}</h2>
                )}
                <ul className="overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-sm">
                  {items.map((item) => (
                    <CartRow key={`${item.class_id}:${item.class_month_id}`} item={item} />
                  ))}
                </ul>
              </section>
            ))}
          </div>

          <aside className="ez-rise lg:sticky lg:top-24" style={{ "--i": 2 } as React.CSSProperties}>
            <div className="flex flex-col gap-5 rounded-ez-lg border border-border bg-surface p-6 shadow-ez-lg">
              <div className="flex flex-col gap-2 text-sm">
                <p className="flex justify-between text-muted">
                  <span>{t("cart.count", { count: cart.items.length })}</span>
                  <span>{t("cart.teachers", { count: new Set(cart.items.map((i) => i.teacher_name)).size })}</span>
                </p>
                {cart.discount_cents > 0 && (
                  <>
                    <p className="flex justify-between border-t border-border pt-3">
                      <span>{t("cart.subtotal")}</span>
                      <span className="tabular-nums">{formatMoney(cart.subtotal_cents, cart.currency)}</span>
                    </p>
                    <p className="flex justify-between font-semibold text-success">
                      <span>{t("cart.discount")}</span>
                      <span className="tabular-nums">−{formatMoney(cart.discount_cents, cart.currency)}</span>
                    </p>
                  </>
                )}
                <p className="flex items-baseline justify-between border-t border-border pt-3">
                  <span className="font-semibold">{t("cart.total")}</span>
                  <span className="font-display text-3xl font-semibold tabular-nums">
                    {formatMoney(cart.total_cents, cart.currency)}
                  </span>
                </p>
              </div>
              <CheckoutButton
                state={!me ? "guest" : !me.phone_verified ? "verify" : cart.ready ? "ready" : "blocked"}
                label={free ? t("cart.checkoutFree") : t("cart.checkout", { amount: formatMoney(cart.total_cents, cart.currency) })}
              />
              {hasCourses && <CouponForm codes={cart.codes} />}
              <p className="flex gap-2 text-xs text-muted">
                <ShieldCheck className="mt-0.5 size-4 shrink-0 text-brand-600" />
                {t("cart.secure")}
              </p>
            </div>
          </aside>
        </div>
      )}
    </SiteShell>
  );
}

function CartRow({ item }: { item: CartItem }) {
  const problem = item.problem
    ? isKnown(item.problem) ? t(`cart.problem.${item.problem}`) : t("cart.problem.other")
    : null;
  return (
    <li className={cx("flex gap-4 border-b border-border p-4 last:border-0 sm:p-5", problem && "bg-warning-bg/40")}>
      <Link href={item.path} className="hidden w-28 shrink-0 overflow-hidden rounded-ez sm:block">
        <ClassCover title={item.title || "?"} subject={item.subject_name} imageUrl={item.cover_image_url} />
      </Link>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <Link href={item.path} className="font-display text-lg leading-snug font-semibold hover:text-brand">
              {item.title || t("cart.problem.UNAVAILABLE")}
            </Link>
            {item.teacher_name && (
              <p className="mt-1 flex min-w-0 items-center gap-2 text-sm text-muted">
                <TeacherAvatar name={item.teacher_name} photo={item.teacher_photo_url} size="sm" />
                <span className="truncate">{t("cart.by", { teacher: item.teacher_name })}</span>
              </p>
            )}
          </div>
          <div className="flex shrink-0 flex-col items-end">
            <p className={cx("font-display text-lg font-semibold whitespace-nowrap tabular-nums", item.discount_cents > 0 && "text-success")}>
              {item.amount_cents !== null
                ? item.amount_cents === 0 ? t("cart.freeItem") : formatMoney(item.amount_cents, item.currency)
                : "—"}
            </p>
            {item.discount_cents > 0 && item.list_price_cents !== null && (
              <p className="text-sm whitespace-nowrap text-muted line-through tabular-nums">{formatMoney(item.list_price_cents, item.currency)}</p>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-sunken px-2.5 py-1 text-xs font-semibold text-foreground">
            <CalendarDays className="size-3.5 text-brand-600" />
            {item.month_start ? formatMonth(item.month_start) : t("cart.oneTime")}
          </span>
          {item.discount_cents > 0 && item.coupon_code && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-success-bg px-2.5 py-1 text-xs font-semibold text-success">
              <Tag className="size-3.5" />
              {item.coupon_public ? t("cart.onSale") : t("cart.codeApplied", { code: item.coupon_code })}
            </span>
          )}
          <form action={removeFromCart.bind(null, item.id, item.class_id, item.class_month_id)}>
            <button className="inline-flex min-h-9 items-center gap-1.5 rounded-ez px-2 text-sm font-medium text-muted hover:bg-sunken hover:text-danger">
              <Trash2 className="size-4" />
              {t("cart.remove")}
            </button>
          </form>
        </div>
        {problem && (
          <p className="flex items-start gap-2 text-sm font-medium text-warning">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            {problem}
          </p>
        )}
      </div>
    </li>
  );
}
