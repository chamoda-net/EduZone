"use client";

import { Tag, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { useT } from "@eduzone/lib/i18n/client";
import { Button, ErrorText, Input, cx } from "@eduzone/ui";

import { applyCoupon, removeCoupon } from "./actions";

/** "Have a coupon?": apply a code; applied codes show as removable chips. */
export function CouponForm({ codes }: { codes: string[] }) {
  const t = useT();
  const router = useRouter();
  const [open, setOpen] = useState(codes.length > 0);
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function apply(e: React.FormEvent) {
    e.preventDefault();
    if (!value.trim()) return;
    setError(null);
    start(async () => {
      const res = await applyCoupon(value);
      if (!res.ok) return setError(res.error);
      setValue("");
      router.refresh();
    });
  }

  function remove(code: string) {
    start(async () => {
      await removeCoupon(code);
      router.refresh();
    });
  }

  return (
    <div className="flex flex-col gap-3 border-t border-border pt-4">
      {codes.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {codes.map((code) => (
            <li key={code} className="inline-flex items-center gap-1.5 rounded-full border border-success/30 bg-success-bg py-1 pr-1 pl-3 text-xs font-bold tracking-wide text-success">
              <Tag className="size-3.5" aria-hidden />
              {code}
              <button type="button" onClick={() => remove(code)} disabled={pending}
                      aria-label={t("cart.coupon.remove", { code })}
                      className="grid size-6 place-items-center rounded-full hover:bg-success/15">
                <X className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {!open ? (
        <button type="button" onClick={() => setOpen(true)}
                className="self-start text-sm font-semibold text-brand underline-offset-4 hover:underline">
          {t("cart.coupon.have")}
        </button>
      ) : (
        <form onSubmit={apply} className="flex flex-col gap-2">
          <label htmlFor="coupon" className="text-sm font-semibold">{t("cart.coupon.label")}</label>
          <div className="flex gap-2">
            <Input id="coupon" value={value} onChange={(e) => setValue(e.target.value.toUpperCase())} maxLength={20}
                   autoComplete="off" spellCheck={false} placeholder={t("cart.coupon.placeholder")}
                   aria-invalid={!!error}
                   className={cx("min-w-0 flex-1 font-mono tracking-wider uppercase placeholder:font-sans placeholder:tracking-normal placeholder:normal-case",
                                 error && "border-danger")} />
            <Button type="submit" variant="outline" loading={pending}>{t("cart.coupon.apply")}</Button>
          </div>
          {error && <ErrorText>{error}</ErrorText>}
        </form>
      )}
    </div>
  );
}
