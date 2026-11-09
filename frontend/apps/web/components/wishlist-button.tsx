"use client";

import { Heart } from "lucide-react";
import { usePathname } from "next/navigation";
import { useState, useTransition } from "react";

import { setSaved } from "@/app/learn/wishlist/actions";
import { useT } from "@eduzone/lib/i18n/client";
import { cx, toast } from "@eduzone/ui";

/** The heart: saves a course to the wishlist (optimistic). `overlay` sits on a card's cover, inside its link. */
export function WishlistButton({ courseId, saved: initial, variant = "button" }: {
  courseId: string;
  saved: boolean;
  variant?: "button" | "overlay";
}) {
  const t = useT();
  const path = usePathname();
  const [saved, setState] = useState(initial);
  const [pending, start] = useTransition();

  function toggle(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    const next = !saved;
    setState(next);
    start(async () => {
      const res = await setSaved(courseId, next, path);
      if (!res.ok) {
        setState(!next);
        toast(res.error);
        return;
      }
      toast(next ? t("wishlist.saved") : t("wishlist.removed"));
    });
  }

  const label = saved ? t("wishlist.remove") : t("wishlist.save");
  if (variant === "overlay") {
    return (
      <button type="button" onClick={toggle} aria-pressed={saved} aria-label={label} title={label} disabled={pending}
              className="grid size-9 place-items-center rounded-full bg-surface/95 text-brand shadow-ez transition hover:scale-105 active:scale-95">
        <Heart className={cx("size-4.5 transition", saved && "fill-danger text-danger")} />
      </button>
    );
  }
  return (
    <button type="button" onClick={toggle} aria-pressed={saved} aria-label={label} title={label} disabled={pending}
            className={cx("grid size-12 shrink-0 place-items-center rounded-ez border transition active:scale-95",
                          saved ? "border-danger/30 bg-danger-bg text-danger" : "border-border-strong text-foreground hover:bg-sunken")}>
      <Heart className={cx("size-5 transition", saved && "fill-danger")} />
    </button>
  );
}
