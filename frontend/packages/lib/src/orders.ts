import type { OrderStatus } from "./types";

/** Badge colours for order status (reuses the shared status palette). */
export const orderTone: Record<OrderStatus, string> = {
  pending: "upcoming",
  paid: "published",
  failed: "draft",
  cancelled: "archived",
  refunded: "archived",
  partially_refunded: "upcoming",
};
