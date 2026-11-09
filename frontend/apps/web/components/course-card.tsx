import { ArrowUpRight, Clock, PlayCircle, Star } from "lucide-react";
import Link from "next/link";

import type { Schema } from "@eduzone/api-client";
import { TeacherAvatar } from "@/components/teacher-avatar";
import { coursePrice, formatLength, isNew } from "@/lib/courses";
import { t } from "@eduzone/lib/i18n";
import { Badge, ClassCover } from "@eduzone/ui";

type MarketCourse = Schema<"MarketCourse">;

/** A course on the marketplace: cover, title, instructor, rating, length, price. */
export function CourseCard({ c, index = 0 }: { c: MarketCourse; index?: number }) {
  const free = c.pricing_model === "free" || !c.one_time_price_cents;
  return (
    <Link
      href={c.path}
      style={{ "--i": index } as React.CSSProperties}
      className="ez-rise group flex flex-col overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-sm transition duration-300 ease-ez hover:-translate-y-1 hover:border-border-strong hover:shadow-ez-lg"
    >
      <div className="relative overflow-hidden">
        <ClassCover title={c.title} subject={c.category_name} imageUrl={c.cover_image_url}
                    label={c.level ? t(`courses.level.${c.level as "all"}`) : null}
                    className="transition duration-500 ease-ez group-hover:scale-[1.03]" />
        <div className="absolute bottom-3 left-3 flex gap-1.5">
          {isNew(c.first_published_at ?? null) && <Badge tone="gold" className="shadow-ez-sm">{t("market.courses.card.new")}</Badge>}
          {free && <Badge tone="success" className="shadow-ez-sm">{t("market.courses.card.free")}</Badge>}
        </div>
        <span className="absolute top-3 right-3 grid size-9 translate-y-1 place-items-center rounded-full bg-surface/95 text-brand opacity-0 shadow-ez transition duration-300 group-hover:translate-y-0 group-hover:opacity-100">
          <ArrowUpRight className="size-4.5" />
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-2.5 p-5">
        <p className="truncate text-xs font-bold tracking-[0.12em] text-brand-600 uppercase">
          {c.parent_category_name ? `${c.parent_category_name} · ${c.category_name}` : c.category_name}
        </p>
        <h3 className="font-display text-xl leading-snug font-semibold text-foreground">{c.title}</h3>
        {c.subtitle && <p className="line-clamp-2 text-sm text-muted">{c.subtitle}</p>}
        <div className="flex min-w-0 items-center gap-2 text-sm text-muted">
          <TeacherAvatar name={c.teacher_name} photo={c.teacher_photo_url ?? null} size="sm" />
          <span className="truncate">{c.teacher_name}</span>
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
          {c.rating_avg != null && c.rating_count > 0 && (
            <span className="inline-flex items-center gap-1 font-semibold text-foreground">
              {c.rating_avg.toFixed(1)}
              <Star className="size-3.5 fill-gold text-gold" aria-hidden />
              <span className="font-normal text-muted">{t("market.courses.card.ratings", { count: c.rating_count })}</span>
            </span>
          )}
          <span className="inline-flex items-center gap-1"><Clock className="size-3.5" aria-hidden />{formatLength(t, c.total_video_seconds)}</span>
          <span className="inline-flex items-center gap-1"><PlayCircle className="size-3.5" aria-hidden />{t("market.courses.card.lectures", { count: c.lecture_count })}</span>
        </div>
        <div className="mt-auto flex items-end justify-between gap-3 border-t border-border pt-4">
          <span className="font-display text-2xl font-semibold whitespace-nowrap tabular-nums">{coursePrice(t, c)}</span>
          {c.students > 0 && (
            <span className="text-xs font-medium whitespace-nowrap text-muted">{t("market.courses.card.students", { count: c.students })}</span>
          )}
        </div>
      </div>
    </Link>
  );
}
