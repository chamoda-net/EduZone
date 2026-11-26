/** Open Graph fields every page shares. Next replaces a parent's `openGraph` with a page's own instead of merging
 * them, so a page that sets `openGraph` spreads this first. */
export const OG_BASE = { siteName: "EduZone", locale: "en_LK" } as const;
