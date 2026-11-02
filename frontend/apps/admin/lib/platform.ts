import type { ApplicationStatus, TenantStatus } from "@eduzone/lib/types";
import type { BadgeTone } from "@eduzone/ui";

/** Badge colours for organization status (reuses the shared status palette). */
export const tenantTone: Record<TenantStatus, string> = {
  active: "published", pending: "upcoming", suspended: "draft", closed: "archived",
};

export const applicationTone: Record<ApplicationStatus, BadgeTone> = {
  submitted: "info", changes_requested: "warning", approved: "success", rejected: "danger",
};

/** "Chrome on Android" from a user agent; good enough to tell a student's phone from a laptop. */
export function deviceLabel(ua: string | null | undefined): string | null {
  if (!ua) return null;
  const browser = /Edg\//.test(ua) ? "Edge" : /OPR\//.test(ua) ? "Opera" : /SamsungBrowser/.test(ua) ? "Samsung Internet"
    : /Firefox\//.test(ua) ? "Firefox" : /Chrome\//.test(ua) ? "Chrome" : /Safari\//.test(ua) ? "Safari" : null;
  const os = /Android/.test(ua) ? "Android" : /iPhone|iPad/.test(ua) ? "iOS" : /Windows/.test(ua) ? "Windows"
    : /Mac OS X/.test(ua) ? "macOS" : /Linux/.test(ua) ? "Linux" : null;
  if (browser && os) return `${browser} · ${os}`;
  return browser ?? os ?? ua.slice(0, 40);
}
