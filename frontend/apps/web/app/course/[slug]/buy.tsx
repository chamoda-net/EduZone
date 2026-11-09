"use client";

import { ArrowRight, GraduationCap, Zap } from "lucide-react";
import Link from "next/link";
import { useState, useTransition } from "react";

import { AddToCartButton } from "@/components/add-to-cart";
import { WishlistButton } from "@/components/wishlist-button";
import { useT } from "@eduzone/lib/i18n/client";
import { Button, ErrorText, buttonStyles } from "@eduzone/ui";

import { buyNow, enrollCourse } from "@/app/learn/courses/actions";

/** The course card's actions: open the course you have, enrol in a free one, or buy a paid one. */
export function CourseActions({ courseId, slug, free, owned, inCart, started, couponCode = null, saved = false }: {
  courseId: string;
  slug: string;
  free: boolean;
  owned: boolean;
  inCart: boolean;
  started: boolean;
  couponCode?: string | null;     // a shared code that gives the best price: carried into the cart
  saved?: boolean;
}) {
  const t = useT();
  const [pending, run] = useTransition();
  const [error, setError] = useState<string | null>(null);

  if (owned) {
    return (
      <div className="flex flex-col gap-2">
        <p className="text-center text-sm font-semibold text-success">{t("market.course.youOwn")}</p>
        <Link href={`/learn/courses/${courseId}`} className={buttonStyles("primary", "lg", "w-full")}>
          {started ? t("market.course.continue") : t("market.course.goToCourse")}
          <ArrowRight className="size-4.5" />
        </Link>
      </div>
    );
  }

  const act = (fn: () => Promise<{ ok: boolean; error?: string }>) => {
    setError(null);
    run(async () => {
      const res = await fn();
      if (!res.ok) setError(res.error ?? t("errors.generic"));
    });
  };

  return (
    <div className="flex flex-col gap-2.5">
      {free ? (
        <Button size="lg" className="w-full" loading={pending} icon={<GraduationCap className="size-4.5" />}
                onClick={() => act(() => enrollCourse(courseId, slug))}>
          {t("market.course.enrolFree")}
        </Button>
      ) : (
        <>
          <Button size="lg" className="w-full" loading={pending} icon={<Zap className="size-4.5" />}
                  onClick={() => act(() => buyNow(courseId, couponCode))}>
            {t("market.course.buyNow")}
          </Button>
          <div className="flex gap-2">
            <div className="min-w-0 flex-1">
              <AddToCartButton block classId={courseId} monthId={null} inCart={inCart} couponCode={couponCode}
                               label={t("market.course.addToCart")} />
            </div>
            <WishlistButton courseId={courseId} saved={saved} />
          </div>
        </>
      )}
      {error && <ErrorText>{error}</ErrorText>}
      <p className="text-center text-xs text-muted">{t("market.course.lifetime")}</p>
    </div>
  );
}
