import { formatMoney } from "@eduzone/lib/format";
import type { MessageKey } from "@eduzone/lib/i18n";

type Translate = (key: MessageKey, values?: Record<string, string | number>) => string;

/** "40 min", "2 h", "6 h 30 min": video length on cards and the landing page. */
export function formatLength(t: Translate, seconds: number): string {
  const total = Math.round(seconds / 60);
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (h === 0) return t("market.time.min", { m });
  return m === 0 ? t("market.time.h", { h }) : t("market.time.hMin", { h, m });
}

export function coursePrice(t: Translate, c: { pricing_model: string; one_time_price_cents: number | null; currency: string }): string {
  return c.pricing_model === "free" || !c.one_time_price_cents ? t("market.courses.card.free")
    : formatMoney(c.one_time_price_cents, c.currency);
}

type Priced = { pricing_model: string; one_time_price_cents: number | null; currency: string;
  sale_price_cents?: number | null };

/** The sale (best public coupon) of a paid course right now: the price, the list price and the percent off. */
export function courseSale(c: Priced): { price: number; list: number; percent: number } | null {
  if (c.pricing_model === "free" || !c.one_time_price_cents || c.sale_price_cents == null) return null;
  if (c.sale_price_cents >= c.one_time_price_cents) return null;
  const percent = Math.round((1 - c.sale_price_cents / c.one_time_price_cents) * 100);
  return { price: c.sale_price_cents, list: c.one_time_price_cents, percent };
}

/** A published course is "new" for its first 30 days. */
export function isNew(firstPublishedAt: string | null): boolean {
  return !!firstPublishedAt && Date.now() - new Date(firstPublishedAt).getTime() < 30 * 24 * 3600 * 1000;
}

export const LEVELS = ["beginner", "intermediate", "advanced", "all"] as const;
export const LENGTHS = ["short", "medium", "long", "extra"] as const;
export const COURSE_SORTS = ["popular", "rating", "newest", "price_low", "price_high"] as const;
