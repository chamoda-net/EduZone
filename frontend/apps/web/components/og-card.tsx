import { BOOK, KEYLINE, LEAVES, LEAVES_LIT, SHIELD, SHIELD_RIM, STEM, SYMBOL_BOX, WORDMARK, WORDMARK_BOX } from "@eduzone/ui/logo-paths";

const dataUri = (svg: string) => `data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`;

/** The logo on dark, as images: ImageResponse draws SVG files more reliably than inline SVG. */
const SYMBOL_SRC = dataUri(
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${SYMBOL_BOX}" width="192" height="228">` +
    `<path fill="#d4a03f" d="${SHIELD}"/><path fill="#124a33" d="${SHIELD_RIM}"/>` +
    `<path fill="#d4a03f" fill-rule="evenodd" d="${KEYLINE}"/><path fill="#d4a03f" d="${STEM} ${LEAVES}"/>` +
    `<path fill="#ecd08f" d="${LEAVES_LIT}"/><path fill="#fbfaf5" d="${BOOK}"/></svg>`,
);
const WORDMARK_SRC = dataUri(
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${WORDMARK_BOX}" width="568" height="75"><path fill="#fbfaf5" d="${WORDMARK}"/></svg>`,
);

/** Share preview (1200×630) for teacher and class pages, drawn with next/og. Inline styles only:
 * ImageResponse supports a small CSS subset and no Tailwind. Colours mirror tokens.css. */
export const OG_SIZE = { width: 1200, height: 630 };

export function OgCard({ eyebrow, title, subtitle, initials }: { eyebrow: string; title: string; subtitle: string; initials: string }) {
  return (
    <div style={{ width: "100%", height: "100%", display: "flex", background: "#0a2a1d", color: "#fbfaf5", padding: 72,
                  flexDirection: "column", justifyContent: "space-between", fontFamily: "serif" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        {/* eslint-disable @next/next/no-img-element, jsx-a11y/alt-text -- drawn into a PNG, not a page */}
        <img src={SYMBOL_SRC} width={76} height={90} />
        <img src={WORDMARK_SRC} width={258} height={34} />
        {/* eslint-enable */}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 48 }}>
        <div style={{ width: 200, height: 200, borderRadius: 100, background: "#d8ece0", color: "#0e3a28", display: "flex",
                      alignItems: "center", justifyContent: "center", fontSize: 84, fontWeight: 700, flexShrink: 0 }}>{initials}</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ fontSize: 28, color: "#d4a03f", letterSpacing: 3, textTransform: "uppercase" }}>{eyebrow}</div>
          <div style={{ fontSize: 66, fontWeight: 700, lineHeight: 1.05, maxWidth: 780 }}>{title}</div>
          <div style={{ fontSize: 30, color: "#8cc3a5", maxWidth: 780 }}>{subtitle}</div>
        </div>
      </div>
      <div style={{ display: "flex", height: 10, background: "#d4a03f", borderRadius: 5, width: 240 }} />
    </div>
  );
}
