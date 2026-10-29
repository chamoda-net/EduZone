// Small shared building blocks. Mobile-first: full-width controls, 44px touch targets.

import type { ComponentProps, ReactNode } from "react";

/** What a form Server Action returns to its form (errors are already translated). */
export type ActionState = { error?: string; ok?: boolean; at?: number };

export const buttonClass = {
  primary:
    "inline-flex min-h-11 items-center justify-center rounded-lg bg-brand px-4 font-medium text-on-brand hover:opacity-90 disabled:opacity-50",
  secondary:
    "inline-flex min-h-11 items-center justify-center rounded-lg border border-border bg-surface px-4 font-medium hover:bg-background disabled:opacity-50",
  danger:
    "inline-flex min-h-11 items-center justify-center rounded-lg border border-danger/40 px-4 font-medium text-danger hover:bg-danger-bg disabled:opacity-50",
  link: "font-medium text-brand hover:underline",
};

export const inputClass =
  "min-h-11 w-full rounded-lg border border-border px-3 outline-none focus:border-brand focus:ring-2 focus:ring-brand/20";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-border bg-surface p-4 sm:p-5 ${className}`}>{children}</section>;
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-sm font-medium">{label}</span>
      {children}
      {hint && <span className="text-xs text-muted">{hint}</span>}
    </label>
  );
}

export function Input(props: ComponentProps<"input">) {
  return <input {...props} className={`${inputClass} ${props.className ?? ""}`} />;
}

export function Select(props: ComponentProps<"select">) {
  return <select {...props} className={`${inputClass} ${props.className ?? ""}`} />;
}

export function ErrorText({ children }: { children?: ReactNode }) {
  if (!children) return null;
  return (
    <p role="alert" className="rounded-lg bg-danger-bg px-3 py-2 text-sm text-danger">
      {children}
    </p>
  );
}

const badgeTone: Record<string, string> = {
  published: "bg-success-bg text-success",
  open: "bg-success-bg text-success",
  draft: "bg-warning-bg text-warning",
  upcoming: "bg-info-bg text-info",
  archived: "bg-border text-muted",
  closed: "bg-border text-muted",
};

export function Badge({ tone, children }: { tone: string; children: ReactNode }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${badgeTone[tone] ?? badgeTone.archived}`}>
      {children}
    </span>
  );
}
