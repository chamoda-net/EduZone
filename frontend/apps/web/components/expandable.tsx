"use client";

import { ChevronDown } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { useT } from "@eduzone/lib/i18n/client";
import { cx } from "@eduzone/ui";

/** Long text folded to `collapsedPx` with a fade and "Show more"; the button appears only when it overflows. */
export function Expandable({ children, collapsedPx = 220 }: { children: ReactNode; collapsedPx?: number }) {
  const t = useT();
  const inner = useRef<HTMLDivElement>(null);
  const [long, setLong] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const el = inner.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setLong(el.scrollHeight > collapsedPx + 40));
    observer.observe(el);
    return () => observer.disconnect();
  }, [collapsedPx]);

  return (
    <div>
      <div className={cx("relative overflow-hidden", long && !open && "[mask-image:linear-gradient(to_bottom,black_60%,transparent)]")}
           style={long && !open ? { maxHeight: collapsedPx } : undefined}>
        <div ref={inner}>{children}</div>
      </div>
      {long && (
        <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
                className="mt-2 inline-flex items-center gap-1 text-sm font-semibold text-brand hover:underline">
          {open ? t("common.showLess") : t("common.showMore")}
          <ChevronDown className={cx("size-4 transition", open && "rotate-180")} />
        </button>
      )}
    </div>
  );
}
