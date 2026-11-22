"use client";

import { ArrowRight, GraduationCap, Zap } from "lucide-react";
import Link from "next/link";
import { useEffect, useState, useTransition } from "react";

import { useT } from "@eduzone/lib/i18n/client";
import { Button, buttonStyles, cx, toast } from "@eduzone/ui";

import { buyNow, enrollCourse } from "@/app/learn/courses/actions";

/** Phones: once the price card has scrolled away, a bar at the bottom keeps the price and the main action in reach.
 * Signed-in students also have the tab bar there, so it sits just above it. */
export function StickyBuyBar({ watchId, price, listPrice, mode, courseId, slug, couponCode, aboveTabs }: {
  watchId: string;
  price: string;
  listPrice: string | null;
  mode: "buy" | "free" | "owned";
  courseId: string;
  slug: string;
  couponCode: string | null;
  aboveTabs: boolean;
}) {
  const t = useT();
  const [show, setShow] = useState(false);
  const [pending, run] = useTransition();

  useEffect(() => {
    const target = document.getElementById(watchId);
    if (!target) return;
    const observer = new IntersectionObserver(([entry]) => setShow(!entry.isIntersecting && entry.boundingClientRect.top < 0));
    observer.observe(target);
    return () => observer.disconnect();
  }, [watchId]);

  const act = (fn: () => Promise<{ ok: boolean; error?: string }>) => run(async () => {
    const res = await fn();
    if (!res.ok && res.error) toast(res.error);
  });

  return (
    <div aria-hidden={!show}
         className={cx("fixed inset-x-0 z-30 border-t border-border bg-surface/95 px-4 py-3 shadow-[0_-8px_24px_-12px_rgb(0_0_0/0.25)] backdrop-blur-md transition duration-300 ease-ez lg:hidden",
                       aboveTabs ? "bottom-[calc(4rem+env(safe-area-inset-bottom))]" : "bottom-0 pb-[max(0.75rem,env(safe-area-inset-bottom))]",
                       show ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-4 opacity-0")}>
      <div className="mx-auto flex max-w-xl items-center justify-between gap-3">
        <p className="flex min-w-0 flex-col leading-tight">
          <span className="font-display text-xl font-semibold tabular-nums">{price}</span>
          {listPrice && <span className="text-xs text-muted line-through tabular-nums">{listPrice}</span>}
        </p>
        {mode === "owned" ? (
          <Link href={`/learn/courses/${courseId}`} tabIndex={show ? 0 : -1} className={buttonStyles("primary", "md")}>
            {t("market.course.goToCourse")}<ArrowRight className="size-4" />
          </Link>
        ) : mode === "free" ? (
          <Button tabIndex={show ? 0 : -1} loading={pending} icon={<GraduationCap className="size-4" />}
                  onClick={() => act(() => enrollCourse(courseId, slug))}>
            {t("market.course.enrolFree")}
          </Button>
        ) : (
          <Button tabIndex={show ? 0 : -1} loading={pending} icon={<Zap className="size-4" />}
                  onClick={() => act(() => buyNow(courseId, couponCode))}>
            {t("market.course.buyNow")}
          </Button>
        )}
      </div>
    </div>
  );
}
