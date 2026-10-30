import Link from "next/link";
import type { ReactNode } from "react";

import { cx } from "./cx";

export type Chip = { href: string; label: ReactNode; active: boolean; count?: number };

/** Filter links that look like pills; scrolls sideways on phones. */
export function FilterChips({ items, className, label }: { items: Chip[]; className?: string; label?: string }) {
  return (
    <nav aria-label={label} className={cx("-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 [scrollbar-width:none] sm:mx-0 sm:px-0", className)}>
      {items.map((c) => (
        <Link
          key={c.href}
          href={c.href}
          aria-current={c.active ? "true" : undefined}
          className={cx(
            "inline-flex min-h-10 shrink-0 items-center gap-2 rounded-full border px-4 text-sm font-semibold whitespace-nowrap transition-all duration-200",
            c.active
              ? "border-brand-800 bg-brand-800 text-on-brand shadow-ez-sm"
              : "border-border-strong bg-surface text-muted hover:border-foreground/40 hover:text-foreground",
          )}
        >
          {c.label}
          {c.count !== undefined && (
            <span className={cx("rounded-full px-1.5 text-xs tabular-nums", c.active ? "bg-brand-700 text-gold-300" : "bg-sunken")}>
              {c.count}
            </span>
          )}
        </Link>
      ))}
    </nav>
  );
}
