import { Star } from "lucide-react";

import { cx } from "@eduzone/ui";

/** A 0-5 star rating, half stars included (display only). */
export function Stars({ value, size = "sm", className }: { value: number; size?: "sm" | "md" | "lg"; className?: string }) {
  const dims = { sm: "size-3.5", md: "size-4.5", lg: "size-6" }[size];
  return (
    <span className={cx("inline-flex gap-0.5", className)} aria-hidden>
      {[1, 2, 3, 4, 5].map((i) => {
        const fill = value >= i - 0.25 ? "full" : value >= i - 0.75 ? "half" : "none";
        return (
          <span key={i} className="relative inline-block">
            <Star className={cx(dims, "text-gold/45")} />
            {fill !== "none" && (
              <span className="absolute inset-0 overflow-hidden" style={{ width: fill === "half" ? "50%" : "100%" }}>
                <Star className={cx(dims, "fill-gold text-gold")} />
              </span>
            )}
          </span>
        );
      })}
    </span>
  );
}
