import { formatDateTime, isoToColomboLocal } from "@eduzone/lib/format";
import { t } from "@eduzone/lib/i18n";
import type { MarketClass } from "@eduzone/lib/types";
import type { BadgeTone } from "@eduzone/ui";

const day = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeZone: "Asia/Colombo" });

/** When something ends. A time at midnight in Sri Lanka reads as the end of the day before it. */
export function deadline(iso: string): string {
  if (!isoToColomboLocal(iso).endsWith("T00:00")) return formatDateTime(iso);
  return t("seats.endOf", { date: day.format(new Date(new Date(iso).getTime() - 60_000)) });
}

/** The last day a moment belongs to (YYYY-MM-DD), for a date input: midnight counts as the day before. */
export function lastDay(iso: string): string {
  return isoToColomboLocal(new Date(new Date(iso).getTime() - 60_000).toISOString()).slice(0, 10);
}

/** What a class card says about seats, if anything. Few seats left are worth saying; plenty are not. */
export function seatBadge(c: Pick<MarketClass, "seat_limit" | "seats_left" | "is_full" | "registration">): { tone: BadgeTone; label: string } | null {
  if (c.registration == null) return null;
  if (c.is_full) return { tone: "danger", label: t("seat.full") };
  if (c.registration === "closed") return { tone: "neutral", label: t("seat.closed") };
  if (c.seats_left != null && c.seat_limit != null && c.seats_left <= Math.max(3, Math.floor(c.seat_limit * 0.3))) {
    return { tone: "warning", label: t("seat.left", { count: c.seats_left }) };
  }
  if (c.registration === "ask") return { tone: "info", label: t("seat.ask") };
  return c.seat_limit != null ? { tone: "brand", label: t("seat.group", { count: c.seat_limit }) } : null;
}
