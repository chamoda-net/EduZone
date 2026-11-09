"use server";

import { revalidatePath } from "next/cache";

import type { Schema } from "@eduzone/api-client";
import { api } from "@/lib/api";
import { teachHref } from "@/lib/workspace";
import { rupeesToCents } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";

export type CouponFormState = { error?: string; ok?: boolean; at?: number };
type Coupon = Schema<"CouponOut">;

const text = (fd: FormData, name: string) => String(fd.get(name) ?? "").trim();

/** The API checks every rule (code format and uniqueness, 90 days at most, own courses for teachers). */
export async function createCoupon(_: CouponFormState, fd: FormData): Promise<CouponFormState> {
  const type = text(fd, "discount_type") === "fixed" ? "fixed" : "percent";
  const value = text(fd, "value");
  const percent = Math.round(Number(value) * 100);
  const amount = rupeesToCents(value);
  if (type === "percent" && !(percent >= 1 && percent <= 10000)) return { error: t("coupons.percentInvalid") };
  if (type === "fixed" && !amount) return { error: t("coupons.amountInvalid") };
  const ends = text(fd, "ends_on");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(ends)) return { error: t("coupons.endsInvalid") };
  const max = text(fd, "max_redemptions");
  const res = await api<Coupon>("~/coupons", {
    method: "POST",
    body: {
      code: text(fd, "code").toUpperCase(),
      course_id: text(fd, "course_id") || null,
      discount_type: type,
      percent_bps: type === "percent" ? percent : null,
      amount_cents: type === "fixed" ? amount : null,
      is_public: fd.get("is_public") === "on",
      max_redemptions: max ? Number(max) : null,
      ends_at: `${ends}T23:59:59+05:30`, // the end of that day in Colombo
    },
  });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath(await teachHref("/coupons"));
  return { ok: true, at: Date.now() };
}

export async function setCouponStatus(id: string, status: "active" | "disabled"): Promise<{ ok: boolean; error?: string }> {
  const res = await api<Coupon>(`~/coupons/${id}`, { method: "PATCH", body: { status } });
  if (!res.ok) return { ok: false, error: errorText(t, res.error) };
  revalidatePath(await teachHref("/coupons"));
  return { ok: true };
}
