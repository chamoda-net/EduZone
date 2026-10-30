import type { ReactNode } from "react";

import { cx } from "./cx";

export type BadgeTone = "neutral" | "brand" | "success" | "warning" | "danger" | "info" | "gold";

const tones: Record<BadgeTone, string> = {
  neutral: "bg-sunken text-muted ring-border",
  brand: "bg-brand-50 text-brand ring-brand-100",
  success: "bg-success-bg text-success ring-success/15",
  warning: "bg-warning-bg text-warning ring-warning/15",
  danger: "bg-danger-bg text-danger ring-danger/15",
  info: "bg-info-bg text-info ring-info/15",
  gold: "bg-gold-100 text-gold-strong ring-gold/25",
};

// Older screens pass status-like names; map them onto tones.
const legacy: Record<string, BadgeTone> = {
  published: "success",
  open: "success",
  draft: "warning",
  upcoming: "info",
  archived: "neutral",
  closed: "neutral",
};

function toneOf(tone: string): BadgeTone {
  return tone in tones ? (tone as BadgeTone) : (legacy[tone] ?? "neutral");
}

export function Badge({
  tone = "neutral",
  dot,
  children,
  className,
}: {
  tone?: BadgeTone | string;
  dot?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap ring-1 ring-inset",
        tones[toneOf(tone)],
        className,
      )}
    >
      {dot && <span aria-hidden className="size-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

/** One clear access state per month (FRONTEND.md section 8, rule 2). */
export type PillState = "paid" | "unpaid" | "pending" | "closed" | "upcoming";

const pill: Record<PillState, BadgeTone> = {
  paid: "success",
  unpaid: "gold",
  pending: "warning",
  closed: "neutral",
  upcoming: "info",
};

export function StatusPill({ state, children }: { state: PillState; children: ReactNode }) {
  return (
    <Badge tone={pill[state]} dot>
      {children}
    </Badge>
  );
}
