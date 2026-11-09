import { Award, Check, ChevronRight, Clock, FileText, Infinity as InfinityIcon, MonitorSmartphone, PlayCircle,
  ScrollText, Star, Users } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import type { Schema } from "@eduzone/api-client";
import { ShareTools } from "@/components/share-tools";
import { SiteShell } from "@/components/shell";
import { TeacherAvatar } from "@/components/teacher-avatar";
import { api } from "@/lib/api";
import { getCart, inCart } from "@/lib/cart";
import { coursePrice, formatLength } from "@/lib/courses";
import { jsonLd, market } from "@/lib/market";
import { getMe } from "@/lib/session";
import { siteOrigin } from "@/lib/site";
import { formatDateTime } from "@eduzone/lib/format";
import { t } from "@eduzone/lib/i18n";
import { ClassCover, Container, cx } from "@eduzone/ui";

import { CourseActions } from "./buy";
import { PreviewDialog } from "./preview";

type Detail = Schema<"MarketCourseDetail">;

const load = async (params: Promise<{ slug: string }>) => market<Detail>(`/course/${(await params).slug}`);

export async function generateMetadata({ params }: PageProps<"/course/[slug]">): Promise<Metadata> {
  const d = await load(params);
  const title = t("market.course.metaTitle", { title: d.course.title });
  const description = t("market.course.metaDescription", { subtitle: d.course.subtitle ?? "", teacher: d.course.teacher_name }).trim();
  return { title, description, openGraph: { title, description, images: d.course.cover_image_url ? [d.course.cover_image_url] : undefined } };
}

const lectureIcon = { recorded: PlayCircle, document: FileText, article: ScrollText } as const;

function Stars({ value }: { value: number }) {
  return (
    <span className="inline-flex" aria-hidden>
      {[1, 2, 3, 4, 5].map((i) => (
        <Star key={i} className={cx("size-4", value >= i - 0.25 ? "fill-gold text-gold" : value >= i - 0.75 ? "fill-gold/50 text-gold" : "text-gold/50")} />
      ))}
    </span>
  );
}

/** /course/<slug>: the course landing page. Previews play for anyone; a paid course is bought through the cart,
 * a free one is enrolled in, and a student who has it goes straight to the player. */
export default async function CourseLandingPage({ params }: PageProps<"/course/[slug]">) {
  const d = await load(params);
  const c = d.course;
  const origin = await siteOrigin();
  const url = `${origin}${c.path}`;
  const lectures = d.sections.flatMap((s) => s.lectures);
  const articles = lectures.filter((l) => l.lesson_type === "article").length;
  const previews = [
    ...(d.has_promo ? [{ id: null, title: c.title, seconds: 0 }] : []),
    ...lectures.filter((l) => l.can_preview).map((l) => ({ id: l.id, title: l.title, seconds: l.video_seconds })),
  ];
  const paid = c.pricing_model === "one_time" && !!c.one_time_price_cents;
  const instructorHref = `/instructor/${d.instructor.slug}`;
  const rating = c.rating_avg != null && c.rating_count > 0 ? c.rating_avg : null;
  // What the card offers this visitor: their course, a free enrolment, or buying it.
  const me = await getMe();
  const mine = me ? await api<Schema<"LearnCourse">>(`/learn/courses/${c.id}`) : null;
  const owned = !!(mine?.ok && mine.data.has_access);
  const cart = !owned && paid ? await getCart() : null;

  const includes = [
    { icon: <PlayCircle />, text: t("market.course.includesVideo", { length: formatLength(t, c.total_video_seconds) }) },
    ...(articles > 0 ? [{ icon: <ScrollText />, text: t("market.course.includesArticles", { count: articles }) }] : []),
    { icon: <MonitorSmartphone />, text: t("market.course.includesDevices") },
    { icon: <InfinityIcon />, text: t("market.course.includesLifetime") },
    ...(paid ? [{ icon: <Award />, text: t("market.course.includesCertificate") }] : []),
  ];

  const card = (
    <div className="overflow-hidden rounded-ez-lg border border-border bg-surface text-foreground shadow-ez-lg">
      {previews.length > 0 ? (
        <PreviewDialog slug={c.slug} items={previews} trigger={
          <button type="button" className="group relative block w-full">
            <ClassCover title={c.title} subject={c.category_name} imageUrl={c.cover_image_url} />
            <span className="absolute inset-0 grid place-items-center bg-brand-950/35 transition group-hover:bg-brand-950/45">
              <span className="grid size-16 place-items-center rounded-full bg-surface text-brand shadow-ez-lg transition group-hover:scale-105">
                <PlayCircle className="size-9" />
              </span>
            </span>
            <span className="absolute inset-x-0 bottom-3 text-center text-sm font-semibold text-on-brand drop-shadow">
              {t("market.course.previewCourse")}
            </span>
          </button>
        } />
      ) : (
        <ClassCover title={c.title} subject={c.category_name} imageUrl={c.cover_image_url} />
      )}
      <div className="flex flex-col gap-4 p-5">
        <p className="font-display text-3xl font-semibold tabular-nums">{coursePrice(t, c)}</p>
        <CourseActions courseId={c.id} slug={c.slug} free={!paid} owned={owned}
                       inCart={!!cart && inCart(cart, c.id, null)}
                       started={!!(mine?.ok && mine.data.progress.completed > 0)} />
        <div>
          <p className="mb-2 text-sm font-semibold">{t("market.course.includes")}</p>
          <ul className="flex flex-col gap-2 text-sm text-foreground/85">
            {includes.map((x) => (
              <li key={x.text} className="flex items-center gap-2.5 [&>svg]:size-4 [&>svg]:shrink-0 [&>svg]:text-brand-600">{x.icon}{x.text}</li>
            ))}
          </ul>
        </div>
        <div className="border-t border-border pt-4">
          <ShareTools url={url} message={t("market.course.shareMessage", { title: c.title })} compact />
        </div>
      </div>
    </div>
  );

  return (
    <SiteShell bare>
      <script type="application/ld+json" dangerouslySetInnerHTML={jsonLd({
        "@context": "https://schema.org", "@type": "Course", name: c.title, url, description: c.subtitle ?? d.description ?? undefined,
        inLanguage: c.language ?? undefined, image: c.cover_image_url ?? undefined,
        provider: { "@type": "Person", name: c.teacher_name, url: `${origin}${instructorHref}` },
        ...(rating ? { aggregateRating: { "@type": "AggregateRating", ratingValue: rating, ratingCount: c.rating_count } } : {}),
        offers: { "@type": "Offer", price: ((c.one_time_price_cents ?? 0) / 100).toFixed(2), priceCurrency: c.currency, category: paid ? "Paid" : "Free" },
        hasCourseInstance: { "@type": "CourseInstance", courseMode: "online", courseWorkload: `PT${Math.round(c.total_video_seconds / 60)}M` },
      })} />

      <section className="ez-grain relative bg-brand-900 text-on-brand">
        <Container className="grid gap-y-8 py-10 sm:py-14 [&>*]:min-w-0">
          <div className="flex max-w-3xl flex-col gap-4">
            <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-1 text-sm font-semibold text-brand-100/80">
              <Link href="/courses" className="hover:text-on-brand">{t("market.course.breadcrumb")}</Link>
              {c.parent_category_slug && (
                <>
                  <ChevronRight className="size-3.5" />
                  <Link href={`/courses/${c.parent_category_slug}`} className="hover:text-on-brand">{c.parent_category_name}</Link>
                </>
              )}
              <ChevronRight className="size-3.5" />
              <Link href={c.parent_category_slug ? `/courses/${c.parent_category_slug}/${c.category_slug}` : `/courses/${c.category_slug}`}
                    className="text-gold-300 hover:text-on-brand">{c.category_name}</Link>
            </nav>
            <h1 className="ez-rise font-display text-4xl leading-[1.05] font-semibold sm:text-5xl">{c.title}</h1>
            {c.subtitle && <p className="ez-rise max-w-2xl text-lg text-brand-100/90" style={{ "--i": 1 } as React.CSSProperties}>{c.subtitle}</p>}
            <div className="ez-rise flex flex-wrap items-center gap-x-4 gap-y-2 text-sm" style={{ "--i": 2 } as React.CSSProperties}>
              {rating ? (
                <span className="inline-flex items-center gap-1.5">
                  <span className="font-bold text-gold-300">{rating.toFixed(1)}</span>
                  <Stars value={rating} />
                  <span className="text-brand-100/80">({t("market.course.ratings", { count: c.rating_count })})</span>
                </span>
              ) : (
                <span className="rounded-full bg-gold/20 px-2.5 py-0.5 text-xs font-semibold text-gold-300">{t("market.course.noRatings")}</span>
              )}
              {c.students > 0 && (
                <span className="inline-flex items-center gap-1.5 text-brand-100/90"><Users className="size-4" />{t("market.courses.card.students", { count: c.students })}</span>
              )}
            </div>
            <p className="ez-rise text-sm text-brand-100/90" style={{ "--i": 3 } as React.CSSProperties}>
              {t("market.course.createdBy")}{" "}
              <Link href={instructorHref} className="font-semibold text-gold-300 underline-offset-2 hover:underline">{c.teacher_name}</Link>
              {c.org_type === "institute" && <span className="text-brand-100/70"> · {c.org_name}</span>}
            </p>
            <p className="ez-rise flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-brand-100/80" style={{ "--i": 4 } as React.CSSProperties}>
              <span className="inline-flex items-center gap-1.5"><Clock className="size-4" />{t("market.course.updated", { date: formatDateTime(c.updated_at).split(",")[0] })}</span>
              {c.language && <span>{t(`medium.${c.language as "en"}`)}</span>}
              {c.level && <span>{t(`courses.level.${c.level as "all"}`)}</span>}
            </p>
          </div>
          <div className="lg:hidden">{card}</div>
        </Container>
      </section>

      <Container className="grid gap-x-12 gap-y-10 py-10 lg:grid-cols-[1fr_380px] [&>*]:min-w-0">
        <div className="flex flex-col gap-10">
          {d.learning_objectives.length > 0 && (
            <section className="rounded-ez-lg border border-border bg-surface p-6 shadow-ez-sm">
              <h2 className="mb-4 font-display text-2xl font-semibold">{t("market.course.learn")}</h2>
              <ul className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
                {d.learning_objectives.map((o) => (
                  <li key={o} className="flex gap-2.5 text-sm"><Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />{o}</li>
                ))}
              </ul>
            </section>
          )}

          <section className="flex flex-col gap-3">
            <h2 className="font-display text-2xl font-semibold">{t("market.course.content")}</h2>
            <p className="text-sm text-muted">
              {t("market.course.contentSummary", { sections: d.sections.length, lectures: lectures.length, length: formatLength(t, c.total_video_seconds) })}
            </p>
            <div className="overflow-hidden rounded-ez-lg border border-border">
              {d.sections.map((s, i) => (
                <details key={s.id} open={i === 0} className="group border-b border-border last:border-b-0">
                  <summary className="flex cursor-pointer list-none items-center gap-3 bg-sunken/60 px-4 py-3.5 font-semibold hover:bg-sunken [&::-webkit-details-marker]:hidden">
                    <ChevronRight className="size-4 shrink-0 transition group-open:rotate-90" aria-hidden />
                    <span className="min-w-0 flex-1">{s.title}</span>
                    <span className="shrink-0 text-xs font-normal text-muted">
                      {t("market.courses.card.lectures", { count: s.lectures.length })}{s.video_seconds > 0 && ` · ${formatLength(t, s.video_seconds)}`}
                    </span>
                  </summary>
                  <ul className="divide-y divide-border bg-surface">
                    {s.lectures.map((l) => {
                      const Icon = lectureIcon[l.lesson_type as keyof typeof lectureIcon] ?? PlayCircle;
                      return (
                        <li key={l.id} className="flex items-center gap-3 px-4 py-2.5 pl-11 text-sm">
                          <Icon className="size-4 shrink-0 text-muted" aria-hidden />
                          <span className="min-w-0 flex-1">{l.title}</span>
                          {l.can_preview && (
                            <PreviewDialog slug={c.slug} items={previews} start={l.id} trigger={
                              <button type="button" className="shrink-0 text-sm font-semibold text-brand underline-offset-2 hover:underline">
                                {t("market.course.preview")}
                              </button>
                            } />
                          )}
                          {l.video_seconds > 0 && (
                            <span className="w-12 shrink-0 text-right text-xs text-muted tabular-nums">
                              {Math.floor(l.video_seconds / 60)}:{String(l.video_seconds % 60).padStart(2, "0")}
                            </span>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </details>
              ))}
            </div>
          </section>

          {d.requirements.length > 0 && (
            <section>
              <h2 className="mb-3 font-display text-2xl font-semibold">{t("market.course.requirements")}</h2>
              <ul className="list-disc space-y-1.5 pl-5 text-[0.9375rem] text-foreground/85">{d.requirements.map((r) => <li key={r}>{r}</li>)}</ul>
            </section>
          )}

          {d.description && (
            <section>
              <h2 className="mb-3 font-display text-2xl font-semibold">{t("market.course.description")}</h2>
              <p className="max-w-3xl text-[0.9375rem] leading-relaxed whitespace-pre-line text-foreground/85">{d.description}</p>
            </section>
          )}

          {d.target_audience.length > 0 && (
            <section>
              <h2 className="mb-3 font-display text-2xl font-semibold">{t("market.course.audience")}</h2>
              <ul className="list-disc space-y-1.5 pl-5 text-[0.9375rem] text-foreground/85">{d.target_audience.map((a) => <li key={a}>{a}</li>)}</ul>
            </section>
          )}

          <section className="flex flex-col gap-4">
            <h2 className="font-display text-2xl font-semibold">{t("market.course.instructor")}</h2>
            <div className="flex flex-col gap-4 rounded-ez-lg border border-border bg-surface p-6 shadow-ez-sm">
              <Link href={instructorHref} className="group flex items-center gap-4">
                <TeacherAvatar name={d.instructor.display_name} photo={d.instructor.photo_url ?? null} size="lg" />
                <div>
                  <p className="font-display text-xl font-semibold text-brand group-hover:underline">{d.instructor.display_name}</p>
                  {d.instructor.headline && <p className="text-sm text-muted">{d.instructor.headline}</p>}
                </div>
              </Link>
              <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-muted">
                {d.instructor.rating_avg != null && (
                  <li className="inline-flex items-center gap-1"><Star className="size-4 fill-gold text-gold" />{d.instructor.rating_avg.toFixed(1)}</li>
                )}
                <li className="inline-flex items-center gap-1"><Users className="size-4" />{t("market.courses.card.students", { count: d.instructor.students })}</li>
                <li className="inline-flex items-center gap-1"><PlayCircle className="size-4" />{t("market.instructor.courseCount", { count: d.instructor.course_count })}</li>
              </ul>
              {d.instructor.bio && <p className="text-[0.9375rem] leading-relaxed whitespace-pre-line text-foreground/85">{d.instructor.bio}</p>}
            </div>
          </section>
        </div>

        <aside className="hidden lg:block">
          <div className="sticky top-24">{card}</div>
        </aside>
      </Container>
    </SiteShell>
  );
}
