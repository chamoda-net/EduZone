import { cx, hashString } from "./cx";
import {
  BOOK,
  BOOK_SMALL,
  KEYLINE,
  LEAVES,
  LEAVES_LIT,
  LEAVES_LIT_SMALL,
  LEAVES_SMALL,
  SHIELD,
  SHIELD_RIM,
  SHIELD_RIM_SMALL,
  STEM,
  STEM_SMALL,
  SYMBOL_BOX,
  WORDMARK,
  WORDMARK_BOX,
} from "./logo-paths";

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

/** The Scholar Shield, EduZone's mark (docs/brand/logo/GUIDELINES.md): a laurel sprig growing out of an open book.
 * The default is the simple cut, made for 16 to 40 px; `detailed` is the full shield, for 48 px and larger. On dark
 * panels (`.ez-grain` sets --ez-logo-rim) the shield gets a gold edge so it stays visible. */
export function LogoMark({ className, detailed = false }: { className?: string; detailed?: boolean }) {
  return (
    <svg viewBox={SYMBOL_BOX} aria-hidden data-logo-mark className={cx("w-auto", className ?? (detailed ? "h-24" : "h-10"))}>
      <path d={SHIELD} fill="var(--ez-logo-rim, var(--ez-brand-700))" />
      <path d={detailed ? SHIELD_RIM : SHIELD_RIM_SMALL} fill="var(--ez-brand-700)" />
      {detailed && <path d={KEYLINE} fillRule="evenodd" fill="var(--ez-gold-500)" />}
      <path d={detailed ? STEM : STEM_SMALL} fill="var(--ez-gold-500)" />
      <path d={detailed ? LEAVES : LEAVES_SMALL} fill="var(--ez-gold-500)" />
      <path d={detailed ? LEAVES_LIT : LEAVES_LIT_SMALL} fill="var(--ez-gold-300)" />
      <path d={detailed ? BOOK : BOOK_SMALL} fill="var(--ez-on-brand)" />
    </svg>
  );
}

/** The name as drawn in the logo (outlined Fraunces capitals), in the current text colour. */
export function Wordmark({ className = "h-4" }: { className?: string }) {
  return (
    <svg viewBox={WORDMARK_BOX} aria-hidden fill="currentColor" className={cx("w-auto", className)}>
      <path d={WORDMARK} />
    </svg>
  );
}

/** Mark and name. EduZone's own name is the drawn wordmark; an organization's name is plain text beside the mark. */
export function Logo({ name = "EduZone", sub, className }: { name?: string; sub?: string; className?: string }) {
  return (
    <span className={cx("flex min-w-0 items-center gap-2.5", className)}>
      <LogoMark className="h-10 shrink-0" />
      <span className="flex min-w-0 flex-col leading-none">
        {name === "EduZone" ? (
          <>
            <span className="sr-only">{name}</span>
            <Wordmark className="h-4 shrink-0 self-start" />
          </>
        ) : (
          <span className="truncate font-display text-[1.2rem] font-semibold tracking-tight">{name}</span>
        )}
        {sub && <span className="mt-1.5 truncate text-[0.7rem] font-semibold tracking-[0.12em] uppercase opacity-70">{sub}</span>}
      </span>
    </span>
  );
}
