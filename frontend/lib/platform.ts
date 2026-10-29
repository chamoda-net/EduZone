import type { TenantStatus } from "./types";

/** Badge colours for organization status (reuses the shared status palette). */
export const tenantTone: Record<TenantStatus, string> = {
  active: "published", pending: "upcoming", suspended: "draft", closed: "archived",
};
