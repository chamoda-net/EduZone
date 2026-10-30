/** Share preview (1200×630) for teacher and class pages, drawn with next/og. Inline styles only:
 * ImageResponse supports a small CSS subset and no Tailwind. Colours mirror tokens.css. */
export const OG_SIZE = { width: 1200, height: 630 };

export function OgCard({ eyebrow, title, subtitle, initials }: { eyebrow: string; title: string; subtitle: string; initials: string }) {
  return (
    <div style={{ width: "100%", height: "100%", display: "flex", background: "#0a2a1d", color: "#fbfaf5", padding: 72,
                  flexDirection: "column", justifyContent: "space-between", fontFamily: "serif" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <div style={{ width: 64, height: 64, borderRadius: 18, background: "#124a33", display: "flex", alignItems: "center",
                      justifyContent: "center", color: "#d4a03f", fontSize: 30, fontWeight: 700 }}>E</div>
        <div style={{ fontSize: 34, fontWeight: 700 }}>EduZone</div>
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
