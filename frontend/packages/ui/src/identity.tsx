import { cx, hashString } from "./cx";

const AVATAR_TONES = [
  "bg-brand-100 text-brand-800",
  "bg-gold-100 text-gold-strong",
  "bg-brand-800 text-gold-300",
  "bg-sunken text-foreground",
  "bg-brand-50 text-brand-600",
];

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters = parts.length > 1 ? [parts[0][0], parts[parts.length - 1][0]] : [...(parts[0] ?? "?")].slice(0, 2);
  return letters.join("").toUpperCase();
}

export function Avatar({ name, size = "md", className }: { name: string; size?: "sm" | "md" | "lg"; className?: string }) {
  const dims = { sm: "size-8 text-xs", md: "size-10 text-sm", lg: "size-14 text-lg" }[size];
  return (
    <span
      aria-hidden
      className={cx(
        "inline-grid shrink-0 place-items-center rounded-full font-semibold ring-2 ring-surface",
        AVATAR_TONES[hashString(name) % AVATAR_TONES.length],
        dims,
        className,
      )}
    >
      {initials(name)}
    </span>
  );
}

/** EduZone mark (placeholder until the brand is announced): an open book whose pages form a leaf. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" aria-hidden className={cx("size-9", className)}>
      <rect width="40" height="40" rx="11" fill="var(--ez-brand-800)" />
      <path d="M20 29c-3.5-2.6-7.6-3.6-12-3.2V11.4c4.4-.4 8.5.6 12 3.2v14.4Z" fill="var(--ez-brand-300)" />
      <path d="M20 29c3.5-2.6 7.6-3.6 12-3.2V11.4c-4.4-.4-8.5.6-12 3.2v14.4Z" fill="var(--ez-gold-500)" />
      <path d="M20 14.6V29" stroke="var(--ez-brand-800)" strokeWidth="1.4" />
      <path d="M23.5 22.5c2-2.4 4.4-3.6 6.5-3.8" stroke="var(--ez-brand-800)" strokeWidth="1.2" strokeLinecap="round" fill="none" />
    </svg>
  );
}

export function Logo({ name = "EduZone", sub, className }: { name?: string; sub?: string; className?: string }) {
  return (
    <span className={cx("flex min-w-0 items-center gap-2.5", className)}>
      <LogoMark className="shrink-0" />
      <span className="flex min-w-0 flex-col leading-none">
        <span className="truncate font-display text-[1.2rem] font-semibold tracking-tight">{name}</span>
        {sub && <span className="mt-1 truncate text-[0.7rem] font-semibold tracking-[0.12em] text-muted uppercase">{sub}</span>}
      </span>
    </span>
  );
}
