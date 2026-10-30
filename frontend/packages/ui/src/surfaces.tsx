import type { ReactNode } from "react";

import { cx } from "./cx";

export function Container({ children, className, size = "lg", id }: {
  children: ReactNode;
  className?: string;
  size?: "sm" | "md" | "lg" | "xl";
  id?: string;
}) {
  const width = { sm: "max-w-md", md: "max-w-3xl", lg: "max-w-6xl", xl: "max-w-7xl" }[size];
  return (
    <div id={id} className={cx("mx-auto w-full px-4 sm:px-6", width, className)}>
      {children}
    </div>
  );
}

export function Card({ children, className, interactive, as: Tag = "section" }: {
  children: ReactNode;
  className?: string;
  interactive?: boolean;
  as?: "section" | "div" | "article" | "li";
}) {
  return (
    <Tag
      className={cx(
        "rounded-ez-lg border border-border bg-surface p-5 shadow-ez-sm sm:p-6",
        interactive && "transition duration-300 ease-ez hover:-translate-y-0.5 hover:border-border-strong hover:shadow-ez",
        className,
      )}
    >
      {children}
    </Tag>
  );
}

export function CardTitle({ children, action, className }: { children: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cx("flex items-center justify-between gap-3", className)}>
      <h2 className="font-display text-xl font-semibold text-foreground">{children}</h2>
      {action}
    </div>
  );
}

/** Top of a screen: small eyebrow, display title, one line of context, actions on the right. */
export function PageHeader({ eyebrow, title, description, actions, className }: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cx("flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="flex min-w-0 flex-col gap-1.5">
        {eyebrow && <p className="text-xs font-bold tracking-[0.14em] text-brand-600 uppercase">{eyebrow}</p>}
        <h1 className="font-display text-3xl leading-tight font-semibold text-foreground sm:text-4xl">{title}</h1>
        {description && <p className="max-w-2xl text-[0.9375rem] text-muted">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

type AlertTone = "danger" | "warning" | "success" | "info";
const alertTone: Record<AlertTone, string> = {
  danger: "border-danger/20 bg-danger-bg text-danger",
  warning: "border-warning/20 bg-warning-bg text-warning",
  success: "border-success/20 bg-success-bg text-success",
  info: "border-info/20 bg-info-bg text-info",
};

export function Alert({ tone = "info", title, children, className }: {
  tone?: AlertTone;
  title?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={cx("rounded-ez border px-4 py-3 text-sm", alertTone[tone], className)}
    >
      {title && <p className="font-semibold">{title}</p>}
      {children && <div className={cx(Boolean(title) && "mt-0.5", "text-foreground/80")}>{children}</div>}
    </div>
  );
}

/** A translated error next to the thing that failed. */
export function ErrorText({ children }: { children?: ReactNode }) {
  if (!children) return null;
  return <Alert tone="danger">{children}</Alert>;
}

/** What to do next when a list is empty (FRONTEND.md: every data screen has four states). */
export function EmptyState({ icon, title, body, action, className }: {
  icon?: ReactNode;
  title: ReactNode;
  body?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "flex flex-col items-center gap-3 rounded-ez-lg border border-dashed border-border-strong bg-surface/60 px-6 py-12 text-center",
        className,
      )}
    >
      {icon && (
        <div className="grid size-14 place-items-center rounded-full bg-brand-50 text-brand ring-8 ring-brand-50/50 [&>svg]:size-6">
          {icon}
        </div>
      )}
      <p className="font-display text-xl font-semibold">{title}</p>
      {body && <p className="max-w-sm text-sm text-muted">{body}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cx("ez-skeleton rounded-ez", className)} />;
}

export function StatTile({ label, value, hint, tone = "plain", icon }: {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "plain" | "brand" | "gold";
  icon?: ReactNode;
}) {
  const toned = {
    plain: "border-border bg-surface",
    brand: "ez-grain border-brand-800 bg-brand-900 text-on-brand",
    gold: "border-gold/30 bg-gold-100",
  }[tone];
  return (
    <div className={cx("relative flex flex-col gap-2 overflow-hidden rounded-ez-lg border p-5 shadow-ez-sm", toned)}>
      <div className="flex items-center justify-between gap-2">
        <p className={cx("text-sm font-medium", tone === "brand" ? "text-brand-100" : "text-muted")}>{label}</p>
        {icon && <span className={cx("[&>svg]:size-4.5", tone === "brand" ? "text-gold" : "text-brand-600")}>{icon}</span>}
      </div>
      <p className="font-display text-3xl font-semibold tracking-tight tabular-nums">{value}</p>
      {hint && <p className={cx("text-xs", tone === "brand" ? "text-brand-100/80" : "text-muted")}>{hint}</p>}
    </div>
  );
}

/** Label/value rows (receipts, details). */
export function DataList({ items, className }: { items: Array<[ReactNode, ReactNode]>; className?: string }) {
  return (
    <dl className={cx("divide-y divide-border", className)}>
      {items.map(([k, v], i) => (
        <div key={i} className="flex items-baseline justify-between gap-4 py-3 text-sm">
          <dt className="text-muted">{k}</dt>
          <dd className="text-right font-medium">{v}</dd>
        </div>
      ))}
    </dl>
  );
}
