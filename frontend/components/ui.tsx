// Small shared building blocks. Mobile-first: full-width controls, 44px touch targets.

import type { ComponentProps, ReactNode } from "react";

export const buttonClass = {
  primary:
    "inline-flex min-h-11 items-center justify-center rounded-lg bg-brand px-4 font-medium text-white hover:opacity-90 disabled:opacity-50",
  secondary:
    "inline-flex min-h-11 items-center justify-center rounded-lg border border-border bg-surface px-4 font-medium hover:bg-background disabled:opacity-50",
  danger:
    "inline-flex min-h-11 items-center justify-center rounded-lg border border-red-300 px-4 font-medium text-red-700 hover:bg-red-50 disabled:opacity-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950",
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
    <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800 dark:bg-red-950 dark:text-red-300">
      {children}
    </p>
  );
}

const badgeTone: Record<string, string> = {
  published: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300",
  open: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300",
  draft: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  upcoming: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300",
  archived: "bg-gray-200 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  closed: "bg-gray-200 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
};

export function Badge({ tone, children }: { tone: string; children: ReactNode }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${badgeTone[tone] ?? badgeTone.archived}`}>
      {children}
    </span>
  );
}
