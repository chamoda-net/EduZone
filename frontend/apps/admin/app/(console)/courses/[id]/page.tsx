import { CheckCircle2, Circle, Eye, EyeOff, FileText, PlayCircle, ScrollText } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import type { Schema } from "@eduzone/api-client";
import { Badge, Card, CardTitle, DataList, ErrorText, buttonClass } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatDateTime, formatMoney } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";

import { decideCourse, unpublishCourse } from "../../../actions";
import { CourseDecision, UnpublishForm } from "./decision";

type CourseDetail = Schema<"CourseDetail">;
type Category = Schema<"CategoryOut">;

const icons = { recorded: PlayCircle, document: FileText, article: ScrollText } as const;
const statusTone = { draft: "neutral", in_review: "info", published: "success", archived: "warning" } as const;

/** One course as the reviewer sees it: landing page, intended learners, curriculum, automatic checks, decision. */
export default async function CourseReviewPage({ params }: PageProps<"/courses/[id]">) {
  const { id } = await params;
  const [res, cats] = await Promise.all([
    api<CourseDetail>(`/platform/courses/${id}`),
    api<Category[]>("/platform/course-categories"),
  ]);
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    return <ErrorText>{errorText(t, res.error)}</ErrorText>;
  }
  const c = res.data;
  const category = cats.ok ? cats.data.find((x) => x.id === c.category_id)?.name_en : undefined;
  const list = (items: string[]) => (
    <ul className="list-disc space-y-1 pl-5 text-sm">{items.map((x) => <li key={x}>{x}</li>)}</ul>
  );

  return (
    <>
      <Link href="/courses" className={`${buttonClass.link} text-sm`}>← {t("platform.courses.back")}</Link>
      <header className="flex flex-col gap-1">
        <h1 className="flex flex-wrap items-center gap-2 font-display text-3xl font-semibold">
          {c.title}
          <Badge tone={statusTone[c.status as keyof typeof statusTone]}>{t(`status.${c.status as "draft"}`)}</Badge>
        </h1>
        <p className="text-sm text-muted">
          {c.tenant_name} · {c.teacher_name} · <span className="font-mono">/course/{c.slug}</span>
          {c.submitted_at && ` · ${t("platform.courses.submitted", { date: formatDateTime(c.submitted_at) })}`}
        </p>
      </header>

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="flex min-w-0 flex-col gap-5">
          <Card className="flex flex-col gap-4">
            <CardTitle>{t("platform.courses.landing")}</CardTitle>
            {c.cover_image_url && (
              // eslint-disable-next-line @next/next/no-img-element -- an instructor-supplied URL, shown as is to review
              <img src={c.cover_image_url} alt="" className="aspect-video w-full max-w-md rounded-ez object-cover" />
            )}
            {c.subtitle && <p className="text-lg">{c.subtitle}</p>}
            <DataList items={[
              [t("courses.category"), category ?? "—"],
              [t("courses.levelLabel"), c.level ? t(`courses.level.${c.level as "all"}`) : "—"],
              [t("courses.language"), c.medium ? t(`medium.${c.medium as "en"}`) : "—"],
              [t("courses.tab.pricing"), c.pricing_model === "free" || !c.one_time_price_cents ? t("courses.pricingFree")
                : formatMoney(c.one_time_price_cents, c.currency)],
              [t("courses.promo"), c.promo_media_id ? "✓" : "—"],
            ]} />
            {c.description && <p className="text-sm leading-relaxed whitespace-pre-line">{c.description}</p>}
          </Card>

          <Card className="flex flex-col gap-4">
            <CardTitle>{t("platform.courses.learners")}</CardTitle>
            <div><p className="mb-1 text-sm font-semibold">{t("courses.objectives")}</p>{list(c.learning_objectives)}</div>
            <div><p className="mb-1 text-sm font-semibold">{t("courses.requirements")}</p>{list(c.requirements)}</div>
            <div><p className="mb-1 text-sm font-semibold">{t("courses.audience")}</p>{list(c.target_audience)}</div>
          </Card>

          <Card className="flex flex-col gap-3">
            <CardTitle>
              {t("platform.courses.curriculum")}{" "}
              <span className="text-sm font-normal text-muted">
                {t("courses.totalLength", { lectures: t("courses.lectures", { count: c.lecture_count }),
                                            minutes: Math.round(c.total_video_seconds / 60) })}
              </span>
            </CardTitle>
            {c.sections.map((s, i) => (
              <div key={s.id} className="rounded-ez border border-border">
                <p className="border-b border-border bg-sunken/50 px-3 py-2 text-sm font-semibold">
                  {t("courses.section", { n: i + 1 })}: {s.title}
                </p>
                <ul className="divide-y divide-border">
                  {s.lectures.map((l) => {
                    const Icon = icons[l.lesson_type as keyof typeof icons] ?? PlayCircle;
                    return (
                      <li key={l.id} className="flex flex-col gap-1 px-3 py-2 text-sm">
                        <div className="flex items-center gap-2">
                          <Icon className="size-4 shrink-0 text-brand-600" aria-hidden />
                          <span className="min-w-0 flex-1">{l.title}</span>
                          {l.video_seconds > 0 && <span className="text-xs text-muted">{t("courses.minutes", { count: Math.round(l.video_seconds / 60) })}</span>}
                          {l.is_free_preview && <Badge tone="gold"><Eye className="size-3" />{t("courses.preview")}</Badge>}
                          {!l.is_published && <Badge tone="neutral"><EyeOff className="size-3" />{t("courses.hidden")}</Badge>}
                        </div>
                        {l.article_body && (
                          <details className="pl-6 text-xs">
                            <summary className="cursor-pointer text-muted">{t("platform.courses.openArticle")}</summary>
                            <pre className="mt-1 max-h-72 overflow-auto rounded-ez bg-sunken p-2 font-mono whitespace-pre-wrap">{l.article_body}</pre>
                          </details>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </Card>
        </div>

        <aside className="flex flex-col gap-4 lg:sticky lg:top-6">
          <Card className="flex flex-col gap-3">
            <CardTitle>{t("platform.courses.checks")}</CardTitle>
            <ul className="flex flex-col gap-1.5 text-sm">
              {c.checks.map((x) => (
                <li key={x.key} className="flex gap-2">
                  {x.ok ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-label="✓" />
                    : <Circle className="mt-0.5 size-4 shrink-0 text-danger" aria-label="✗" />}
                  <span className={x.ok ? "text-muted" : ""}>
                    {t(`courses.check.${x.key}` as Parameters<typeof t>[0], { current: x.current ?? 0, required: x.required ?? 0 })}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
          {c.status === "in_review" && (
            <Card className="flex flex-col gap-3">
              <CardTitle>{t("platform.courses.decision")}</CardTitle>
              <CourseDecision action={decideCourse.bind(null, c.id)} canApprove={c.ready_to_submit} />
            </Card>
          )}
          {c.status === "published" && (
            <Card className="flex flex-col gap-3">
              <CardTitle>{t("platform.courses.unpublish")}</CardTitle>
              <p className="text-sm text-muted">{t("platform.courses.unpublishHint")}</p>
              <UnpublishForm action={unpublishCourse.bind(null, c.id)} />
            </Card>
          )}
          {c.review_note && c.status !== "in_review" && (
            <Card><p className="text-sm"><span className="font-semibold">{t("courses.reviewNoteFrom")}:</span> {c.review_note}</p></Card>
          )}
          <Link href={`/audit?entity_id=${c.id}`} className={`${buttonClass.link} self-start text-sm`}>{t("platform.nav.audit")} →</Link>
        </aside>
      </div>
    </>
  );
}
