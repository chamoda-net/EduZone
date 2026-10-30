import { cx, hashString } from "./cx";

// Book-cover artwork for classes without an uploaded cover: a palette and a pattern picked
// from the class name, with the subject's initial set large in the display face.
const PALETTES = [
  { bg: "#0e3a28", ink: "#d4a03f", soft: "#17603f", text: "#fbfaf5" },
  { bg: "#124a33", ink: "#ecd08f", soft: "#23805a", text: "#fbfaf5" },
  { bg: "#f2eee4", ink: "#124a33", soft: "#d8ece0", text: "#0a2a1d" },
  { bg: "#d4a03f", ink: "#0a2a1d", soft: "#ecd08f", text: "#0a2a1d" },
  { bg: "#0a2a1d", ink: "#8cc3a5", soft: "#124a33", text: "#fbfaf5" },
  { bg: "#edf6f0", ink: "#17603f", soft: "#d8ece0", text: "#0a2a1d" },
] as const;

const GLYPHS: Record<string, string> = {
  physics: "Φ",
  chemistry: "⚗",
  biology: "β",
  mathematics: "∑",
  maths: "∑",
  "combined maths": "∫",
  science: "λ",
  ict: "<>",
  english: "Aa",
  accounting: "%",
  economics: "€",
};

function glyphFor(subject: string | null | undefined, title: string): string {
  const key = (subject ?? "").trim().toLowerCase();
  if (GLYPHS[key]) return GLYPHS[key];
  // First letter (any script), skipping digits and punctuation: "2028 O/L ගණිතය" → "O".
  const source = subject?.trim() || title.trim();
  return source.match(/\p{L}/u)?.[0]?.toUpperCase() ?? "E";
}

export function ClassCover({
  title,
  subject,
  imageUrl,
  label,
  className,
  size = "md",
}: {
  title: string;
  subject?: string | null;
  imageUrl?: string | null;
  label?: string | null;
  className?: string;
  size?: "sm" | "md" | "lg";
}) {
  if (imageUrl) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- covers come from our CDN at any size
      <img src={imageUrl} alt="" loading="lazy" className={cx("aspect-[16/10] w-full object-cover", className)} />
    );
  }
  const h = hashString(`${subject ?? ""}|${title}`);
  const p = PALETTES[h % PALETTES.length];
  const pattern = (h >> 4) % 3;
  const glyph = glyphFor(subject, title);
  const id = `c${h.toString(36)}`;
  const glyphSize = size === "lg" ? 150 : size === "sm" ? 96 : 120;

  return (
    <svg
      viewBox="0 0 320 200"
      role="img"
      aria-label={title}
      preserveAspectRatio="xMidYMid slice"
      className={cx("block aspect-[16/10] w-full", className)}
    >
      <defs>
        <pattern id={`${id}-dots`} width="14" height="14" patternUnits="userSpaceOnUse">
          <circle cx="2" cy="2" r="1.2" fill={p.ink} opacity="0.35" />
        </pattern>
        <linearGradient id={`${id}-fade`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={p.soft} stopOpacity="0.9" />
          <stop offset="1" stopColor={p.bg} stopOpacity="0" />
        </linearGradient>
      </defs>
      <rect width="320" height="200" fill={p.bg} />
      {pattern === 0 && (
        <>
          <circle cx="250" cy="40" r="110" fill={`url(#${id}-fade)`} />
          <circle cx="250" cy="40" r="70" fill="none" stroke={p.ink} strokeOpacity="0.5" strokeWidth="1.5" />
          <circle cx="250" cy="40" r="96" fill="none" stroke={p.ink} strokeOpacity="0.25" strokeWidth="1" />
        </>
      )}
      {pattern === 1 && (
        <>
          <rect x="170" y="-20" width="180" height="240" fill={`url(#${id}-dots)`} />
          <path d="M150 200 Q 230 90 330 120" fill="none" stroke={p.ink} strokeOpacity="0.6" strokeWidth="2" />
        </>
      )}
      {pattern === 2 && (
        <>
          {Array.from({ length: 7 }, (_, i) => (
            <line key={i} x1={150 + i * 26} y1="0" x2={110 + i * 26} y2="200" stroke={p.ink} strokeOpacity="0.22" strokeWidth="10" />
          ))}
          <rect x="0" y="150" width="320" height="50" fill={p.soft} opacity="0.5" />
        </>
      )}
      {/* Spine */}
      <rect x="0" y="0" width="10" height="200" fill={p.ink} opacity="0.9" />
      <rect x="14" y="0" width="2" height="200" fill={p.ink} opacity="0.4" />
      <text
        x="300"
        y="178"
        textAnchor="end"
        fontFamily="var(--font-display-serif), Georgia, serif"
        fontSize={glyphSize}
        fontStyle="italic"
        fontWeight="600"
        fill={p.ink}
        opacity="0.95"
      >
        {glyph}
      </text>
      {label && (
        <text
          x="32"
          y="38"
          fontFamily="var(--font-body), system-ui, sans-serif"
          fontSize="13"
          fontWeight="700"
          letterSpacing="2"
          fill={p.text}
          opacity="0.85"
        >
          {label.toUpperCase()}
        </text>
      )}
    </svg>
  );
}
