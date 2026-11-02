import { GraduationCap, Plus } from "lucide-react";
import Link from "next/link";

import type { Schema } from "@eduzone/api-client";
import { api } from "@/lib/api";
import { teachHref } from "@/lib/workspace";
import { formatMoney } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import { Badge, ClassCover, EmptyState, ErrorText, PageHeader, buttonStyles } from "@eduzone/ui";

type CourseRow = Schema<"CourseRow">;

const tone = { draft: "draft", in_review: "upcoming", published: "published", archived: "archived" } as const;

/** The organization's courses (a teacher sees only their own). */
export default async function CoursesPage() {
  const base = await teachHref();
  const res = await api<CourseRow[]>("~/courses");
  const newCourse = (
    <Link href={`${base}/courses/new`} className={buttonStyles("primary")}>
      <Plus className="size-4.5" />
      {t("courses.new")}
    </Link>
  );

  return (
    <>
      <PageHeader eyebrow={t("shell.console")} title={t("courses.title")} description={t("courses.subtitle")}
                  actions={newCourse} />
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.length === 0 && (
        <EmptyState icon={<GraduationCap />} title={t("courses.empty")} body={t("courses.emptyBody")} action={newCourse} />
      )}
      {res.ok && res.data.length > 0 && (
        <ul className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {res.data.map((c, i) => (
            <li key={c.id} className="ez-rise" style={{ "--i": i } as React.CSSProperties}>
              <Link
                href={`${base}/courses/${c.id}`}
                className="group flex h-full flex-col overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-sm transition duration-300 ease-ez hover:-translate-y-0.5 hover:shadow-ez-lg"
              >
                <div className="relative">
                  <ClassCover title={c.title} subject={null} imageUrl={c.cover_image_url} size="sm" />
                  <Badge tone={tone[c.status as keyof typeof tone]} dot className="absolute top-3 right-3 shadow-ez-sm">
                    {t(`status.${c.status as keyof typeof tone}`)}
                  </Badge>
                </div>
                <div className="flex flex-1 flex-col gap-2 p-5">
                  <p className="font-display text-lg leading-snug font-semibold">{c.title}</p>
                  {c.subtitle && <p className="line-clamp-2 text-sm text-muted">{c.subtitle}</p>}
                  <p className="text-xs text-muted">
                    {t("courses.totalLength", {
                      lectures: t("courses.lectures", { count: c.lecture_count }),
                      minutes: Math.round(c.total_video_seconds / 60),
                    })}
                    {" · "}{c.teacher_name}
                  </p>
                  <p className="mt-auto pt-2 text-sm font-semibold tabular-nums">
                    {c.pricing_model === "free" || !c.one_time_price_cents
                      ? t("courses.pricingFree") : formatMoney(c.one_time_price_cents, c.currency)}
                  </p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
