import type { ApplicationStatus, TenantStatus } from "@eduzone/lib/types";
import type { BadgeTone } from "@eduzone/ui";

/** Badge colours for organization status (reuses the shared status palette). */
export const tenantTone: Record<TenantStatus, string> = {
  active: "published", pending: "upcoming", suspended: "draft", closed: "archived",
};

export const applicationTone: Record<ApplicationStatus, BadgeTone> = {
  submitted: "info", changes_requested: "warning", approved: "success", rejected: "danger",
};
