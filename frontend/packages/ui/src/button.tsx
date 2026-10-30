import type { ComponentProps, ReactNode } from "react";

import { cx } from "./cx";

export type ButtonVariant = "primary" | "secondary" | "outline" | "ghost" | "danger" | "gold" | "link";
export type ButtonSize = "sm" | "md" | "lg";

const base =
  "group/btn relative inline-flex items-center justify-center gap-2 rounded-ez font-semibold whitespace-nowrap " +
  "transition-[background-color,border-color,color,box-shadow,transform] duration-200 ease-ez " +
  "active:translate-y-px disabled:pointer-events-none disabled:opacity-50 select-none";

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-brand text-on-brand shadow-[inset_0_1px_0_rgb(255_255_255/0.12),0_1px_2px_rgb(6_25_15/0.3)] hover:bg-brand-hover",
  secondary:
    "border border-border-strong bg-surface text-foreground shadow-ez-sm hover:border-foreground/40 hover:bg-sunken/60",
  outline: "border border-brand/30 bg-transparent text-brand hover:border-brand hover:bg-brand-50",
  ghost: "text-foreground hover:bg-sunken",
  danger: "border border-danger/30 bg-surface text-danger hover:border-danger hover:bg-danger-bg",
  gold: "bg-gold text-brand-950 shadow-[inset_0_1px_0_rgb(255_255_255/0.35)] hover:bg-gold-300",
  link: "min-h-0! px-0! text-brand underline-offset-4 hover:underline",
};

const sizes: Record<ButtonSize, string> = {
  sm: "min-h-9 px-3 text-sm",
  md: "min-h-11 px-4.5 text-[0.9375rem]",
  lg: "min-h-13 px-6 text-base",
};

/** Class names for anything that should look like a button (links included). */
export function buttonStyles(variant: ButtonVariant = "primary", size: ButtonSize = "md", className?: string): string {
  return cx(base, sizes[size], variants[variant], className);
}

/** Shortcuts used across the screens. */
export const buttonClass = {
  primary: buttonStyles("primary"),
  secondary: buttonStyles("secondary"),
  outline: buttonStyles("outline"),
  ghost: buttonStyles("ghost"),
  danger: buttonStyles("danger"),
  gold: buttonStyles("gold"),
  link: buttonStyles("link"),
} as const;

export function Spinner({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className={cx("size-4 animate-spin", className)}>
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

type ButtonProps = ComponentProps<"button"> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: ReactNode;
  iconRight?: ReactNode;
};

export function Button({ variant, size, loading, icon, iconRight, className, children, disabled, ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={buttonStyles(variant, size, className)}
    >
      {loading ? <Spinner /> : icon}
      {children}
      {iconRight}
    </button>
  );
}
