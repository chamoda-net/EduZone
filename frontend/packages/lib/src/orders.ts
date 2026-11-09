import type { OrderStatus } from "./types";

/** Badge colours for order status (reuses the shared status palette). */
/** Where a paid item opens: a course in the course player, a class on its class page. */
export function learnHref(item: { class_id: string; kind?: string }): string {
  return item.kind === "course" ? `/learn/courses/${item.class_id}` : `/learn/classes/${item.class_id}`;
}

export const orderTone: Record<OrderStatus, string> = {
  pending: "upcoming",
  paid: "published",
  failed: "draft",
  cancelled: "archived",
  refunded: "archived",
  partially_refunded: "upcoming",
};
