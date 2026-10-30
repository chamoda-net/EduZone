import { ChevronRight, Lock, Video } from "lucide-react";
import Link from "next/link";

import { formatDateTime } from "@eduzone/lib/format";
import { t } from "@eduzone/lib/i18n";
import type { UpcomingLesson } from "@eduzone/lib/types";
import { Badge, cx } from "@eduzone/ui";

const dayFmt = new Intl.DateTimeFormat("en", { day: "numeric", timeZone: "Asia/Colombo" });
const monFmt = new Intl.DateTimeFormat("en", { month: "short", timeZone: "Asia/Colombo" });

/** One upcoming live lesson: date tile, what and whose, and the one next step. */
export function LessonSlot({ l, i = 0 }: { l: UpcomingLesson; i?: number }) {
  const start = new Date(l.scheduled_at);
  const live = l.unlocked && l.live_now;
  const href = l.unlocked ? `/learn/lessons/${l.lesson_id}` : `/learn/classes/${l.class_id}`;

  return (
    <li className="ez-rise" style={{ "--i": i } as React.CSSProperties}>
      <Link
        href={href}
        className={cx(
          "group flex items-center gap-4 rounded-ez-lg border bg-surface p-4 shadow-ez-sm transition hover:-translate-y-0.5 hover:shadow-ez",
          live ? "border-brand/40 ring-4 ring-brand-50" : "border-border",
        )}
      >
        <span className={cx("grid size-14 shrink-0 place-items-center rounded-ez text-center leading-none",
          live ? "bg-brand text-on-brand" : "bg-brand-900 text-on-brand")}>
          <span>
            <span className="block text-[0.7rem] font-bold tracking-widest uppercase opacity-80">{monFmt.format(start)}</span>
            <span className="block font-display text-xl font-semibold">{dayFmt.format(start)}</span>
          </span>
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-semibold">{l.title}</span>
          <span className="block truncate text-sm text-muted">{l.class_title} · {l.org.name}</span>
          <span className="mt-1 flex items-center gap-1.5 text-xs font-medium text-muted">
            <Video className="size-3.5" />
            {formatDateTime(l.scheduled_at)}
          </span>
        </span>
        {live ? (
          <Badge tone="success" dot className="animate-pulse">{t("learn.today.live")}</Badge>
        ) : l.unlocked ? (
          <ChevronRight className="size-5 shrink-0 text-subtle transition-transform group-hover:translate-x-0.5 group-hover:text-brand" />
        ) : (
          <span className="inline-flex shrink-0 items-center gap-1 text-xs font-semibold text-gold-strong">
            <Lock className="size-3.5" />
            {t("learn.today.locked")}
          </span>
        )}
      </Link>
    </li>
  );
}
