import { CheckCircle2, PlayCircle } from "lucide-react";
import Link from "next/link";

import type { Schema } from "@eduzone/api-client";
import { t } from "@eduzone/lib/i18n";
import { ClassCover, cx } from "@eduzone/ui";

type MyCourse = Schema<"MyCourse">;

/** A course in "My learning": cover, title, progress bar and the way back in. */
export function MyCourseCard({ c, index = 0 }: { c: MyCourse; index?: number }) {
  const p = c.progress;
  const done = p.total > 0 && p.percent === 100;
  const href = c.next_lecture_id ? `/learn/courses/${c.id}?lecture=${c.next_lecture_id}` : `/learn/courses/${c.id}`;
  return (
    <Link href={href} style={{ "--i": index } as React.CSSProperties}
          className="ez-rise group flex flex-col overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-sm transition duration-300 ease-ez hover:-translate-y-0.5 hover:shadow-ez-lg">
      <div className="relative">
        <ClassCover title={c.title} subject={null} imageUrl={c.cover_image_url} size="sm" />
        <span className="absolute inset-0 grid place-items-center bg-brand-950/0 transition group-hover:bg-brand-950/35">
          <PlayCircle className="size-12 text-on-brand opacity-0 drop-shadow transition group-hover:opacity-100" />
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <p className="font-display text-lg leading-snug font-semibold">{c.title}</p>
        <p className="truncate text-xs text-muted">{c.teacher_name} · {c.org_name}</p>
        <div className="mt-auto flex flex-col gap-1.5 pt-2">
          <div className="h-1.5 overflow-hidden rounded-full bg-sunken" aria-hidden>
            <div className={cx("h-full rounded-full", done ? "bg-success" : "bg-brand")} style={{ width: `${p.percent}%` }} />
          </div>
          <p className="flex items-center justify-between gap-2 text-xs">
            <span className={cx("font-semibold", done ? "text-success" : "text-muted")}>
              {done ? <span className="inline-flex items-center gap-1"><CheckCircle2 className="size-3.5" />{t("learnCourses.done")}</span>
                : p.completed === 0 ? t("learnCourses.notStarted") : t("learnCourses.percent", { percent: p.percent })}
            </span>
            <span className="font-semibold text-brand">{p.completed === 0 ? t("learnCourses.start") : t("learnCourses.resume")}</span>
          </p>
        </div>
      </div>
    </Link>
  );
}
