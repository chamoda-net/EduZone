"use client";

import { Link2, Percent, Shuffle, Wallet } from "lucide-react";
import { useActionState, useEffect, useRef, useState, useTransition } from "react";

import { useT } from "@eduzone/lib/i18n/client";
import { Button, Checkbox, ErrorText, Field, Input, Select, cx, toast } from "@eduzone/ui";

import { createCoupon, setCouponStatus, type CouponFormState } from "./actions";

type CourseOption = { id: string; title: string };

const ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
const randomCode = () => Array.from({ length: 8 }, () => ALPHABET[Math.floor(Math.random() * ALPHABET.length)]).join("");

/** A date input value N days from today in Colombo. */
function colomboDate(days: number): string {
  return new Date(Date.now() + days * 86_400_000 + 5.5 * 3_600_000).toISOString().slice(0, 10);
}

export function NewCouponForm({ courses, allowAll }: { courses: CourseOption[]; allowAll: boolean }) {
  const t = useT();
  const [state, submit, pending] = useActionState<CouponFormState, FormData>(createCoupon, {});
  const [type, setType] = useState<"percent" | "fixed">("percent");
  const [code, setCode] = useState("");
  const form = useRef<HTMLFormElement>(null);
  const shown = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (state.ok && state.at !== shown.current) {
      shown.current = state.at;
      toast(t("coupons.created"));
      form.current?.reset();
      setCode("");
    }
  }, [state, t]);

  return (
    <form ref={form} action={submit} className="flex flex-col gap-4">
      <Field label={t("coupons.code")} hint={t("coupons.codeHint")} htmlFor="coupon-code">
        <div className="flex gap-2">
          <Input id="coupon-code" name="code" required minLength={4} maxLength={20} pattern="[A-Za-z0-9\-]{4,20}" value={code}
                 onChange={(e) => setCode(e.target.value.toUpperCase())} autoComplete="off" spellCheck={false}
                 className="min-w-0 flex-1 font-mono tracking-wider uppercase" />
          <Button type="button" variant="outline" icon={<Shuffle className="size-4" />} onClick={() => setCode(randomCode())}>
            {t("coupons.generate")}
          </Button>
        </div>
      </Field>
      <Field label={t("coupons.course")}>
        <Select name="course_id" required={!allowAll} defaultValue={courses[0]?.id ?? ""}>
          {allowAll && <option value="">{t("coupons.allCourses")}</option>}
          {courses.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
        </Select>
      </Field>
      <fieldset className="flex flex-col gap-1.5">
        <legend className="mb-1.5 text-sm font-semibold">{t("coupons.discount")}</legend>
        <div className="grid grid-cols-2 gap-1 rounded-ez bg-sunken p-1">
          {(["percent", "fixed"] as const).map((k) => (
            <label key={k} className={cx("flex min-h-10 cursor-pointer items-center justify-center gap-2 rounded-ez text-sm font-semibold transition",
                                         type === k ? "bg-surface text-foreground shadow-ez-sm" : "text-muted hover:text-foreground")}>
              <input type="radio" name="discount_type" value={k} checked={type === k} onChange={() => setType(k)} className="sr-only" />
              {k === "percent" ? <Percent className="size-4" /> : <Wallet className="size-4" />}
              {t(`coupons.type.${k}`)}
            </label>
          ))}
        </div>
        <div className="relative mt-1">
          <Input name="value" required inputMode="decimal" aria-label={t("coupons.discount")}
                 placeholder={type === "percent" ? "20" : "1,000.00"} className={type === "percent" ? "pr-10" : "pl-12"} />
          <span className={cx("pointer-events-none absolute top-1/2 -translate-y-1/2 text-sm font-semibold text-muted",
                              type === "percent" ? "right-3.5" : "left-3.5")}>
            {type === "percent" ? "%" : "Rs."}
          </span>
        </div>
      </fieldset>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("coupons.ends")} hint={t("coupons.endsHint")}>
          <Input type="date" name="ends_on" required defaultValue={colomboDate(30)} min={colomboDate(0)} max={colomboDate(89)} />
        </Field>
        <Field label={t("coupons.limit")} optional={t("coupons.optional")} hint={t("coupons.limitHint")}>
          <Input type="number" name="max_redemptions" min={1} max={1000000} inputMode="numeric" />
        </Field>
      </div>
      <div className="rounded-ez border border-border bg-sunken/50 p-3.5">
        <Checkbox name="is_public" label={
          <>
            <span className="font-semibold">{t("coupons.public")}</span>
            <span className="mt-0.5 block text-muted">{t("coupons.publicHint")}</span>
          </>
        } />
      </div>
      {state.error && <ErrorText>{state.error}</ErrorText>}
      <Button type="submit" loading={pending} className="self-start">{t("coupons.create")}</Button>
    </form>
  );
}

export function CouponToggle({ id, active }: { id: string; active: boolean }) {
  const t = useT();
  const [pending, start] = useTransition();
  return (
    <Button variant="ghost" size="sm" loading={pending} onClick={() => start(async () => {
      const res = await setCouponStatus(id, active ? "disabled" : "active");
      if (!res.ok) toast(res.error ?? t("coupons.failed"));
    })}>
      {active ? t("coupons.disable") : t("coupons.enable")}
    </Button>
  );
}

/** Copies the course page link that carries the code (?coupon=). */
export function CopyCouponLink({ url }: { url: string }) {
  const t = useT();
  return (
    <Button variant="ghost" size="sm" icon={<Link2 className="size-4" />} onClick={async () => {
      try {
        await navigator.clipboard.writeText(url);
        toast(t("coupons.linkCopied"));
      } catch {
        toast(t("share.copyFailed"));
      }
    }}>
      {t("coupons.copyLink")}
    </Button>
  );
}
