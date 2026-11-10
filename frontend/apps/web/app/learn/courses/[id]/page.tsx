import { ArrowLeft, ArrowRight, Award, CheckCircle2, ChevronDown, Circle, Download, FileText, Lock, PartyPopper, PlayCircle,
  ScrollText, Sparkles } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import type { Schema } from "@eduzone/api-client";
import { Markdown } from "@/components/markdown";
import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { formatLength } from "@/lib/courses";
import { getMe } from "@/lib/session";
import { errorText, t } from "@eduzone/lib/i18n";
import type { StudentResource } from "@eduzone/lib/types";
import { Container, ErrorText, buttonStyles, cx } from "@eduzone/ui";

import { PdfResource } from "@/app/learn/lessons/[id]/player";

import { CompleteButton, LectureVideo, RatingCard } from "./client";
import { RefundCard } from "./refund";

type Course = Schema<"LearnCourse">;
type Lecture = Schema<"LectureDetail">;

export const metadata: Metadata = { robots: { index: false } };

const icons = { recorded: PlayCircle, document: FileText, article: ScrollText } as const;

/** The course player: the lecture (video, article or PDF) with "Mark as complete" and previous/next, and the
 * curriculum beside it with ticks and progress. `?lecture=` picks the lecture; without it, where they left off. */
export default async function CoursePlayerPage({ params, searchParams }: PageProps<"/learn/courses/[id]">) {
  const { id } = await params;
  const sp = await searchParams;
  if (!(await getMe())) redirect(`/login?next=${encodeURIComponent(`/learn/courses/${id}`)}`);
  const res = await api<Course>(`/learn/courses/${id}`);
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    return <SiteShell><ErrorText>{errorText(t, res.error)}</ErrorText></SiteShell>;
  }
  const c = res.data;
  const all = c.sections.flatMap((s) => s.lectures);
  const wanted = typeof sp.lecture === "string" ? sp.lecture : null;
  const currentId = (wanted && all.some((l) => l.id === wanted) ? wanted : null)
    ?? c.next_lecture_id ?? all.find((l) => l.unlocked)?.id ?? all[0]?.id;
  const lectureRes = currentId ? await api<Lecture>(`/learn/lectures/${currentId}`) : null;
  const lecture = lectureRes?.ok ? lectureRes.data : null;
  const href = (lectureId: string) => `/learn/courses/${c.id}?lecture=${lectureId}`;
  const p = c.progress;
  // "Rate this course" after a quarter of it, or as soon as they have rated (docs/COURSES.md section 6).
  const askRating = c.has_access && (p.percent >= 25 || c.my_rating != null);
  const reviewRes = askRating ? await api<Schema<"MyReview"> | null>(`/learn/courses/${c.id}/review`) : null;

  return (
    <SiteShell bare>
      <div className="border-b border-border bg-brand-900 text-on-brand">
        <Container className="flex flex-wrap items-center justify-between gap-3 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <Link href={c.path} className="inline-flex shrink-0 items-center gap-1.5 text-sm font-semibold text-brand-100/80 hover:text-on-brand">
              <ArrowLeft className="size-4" />{t("player.course.back")}
            </Link>
            <span className="hidden h-5 w-px bg-brand-700 sm:block" aria-hidden />
            <p className="truncate font-display text-lg font-semibold">{c.title}</p>
          </div>
          {c.has_access && p.total > 0 && (
            <div className="flex items-center gap-3 text-sm">
              <div className="h-2 w-32 overflow-hidden rounded-full bg-brand-800" aria-hidden>
                <div className={cx("h-full rounded-full", p.percent === 100 ? "bg-gold" : "bg-gold-300")} style={{ width: `${p.percent}%` }} />
              </div>
              <span className="text-brand-100/90 tabular-nums">{t("player.course.progress", { completed: p.completed, total: p.total })}</span>
            </div>
          )}
        </Container>
      </div>

      <Container className="grid gap-8 py-6 lg:grid-cols-[minmax(0,1fr)_22rem] [&>*]:min-w-0">
        <main className="flex flex-col gap-5">
          {c.certificate_no && (
            <div className="ez-grain flex flex-col gap-3 rounded-ez-lg bg-brand-900 p-5 text-on-brand sm:flex-row sm:items-center sm:justify-between">
              <div className="flex gap-3">
                <Award className="mt-0.5 size-6 shrink-0 text-gold" />
                <div>
                  <p className="font-display text-lg font-semibold">{t("cert.ready")}</p>
                  <p className="text-sm text-brand-100/80">{t("cert.readyBody")}</p>
                </div>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                <Link href={`/certificates/${c.certificate_no}`} className={buttonStyles("gold", "sm")}>{t("cert.view")}</Link>
                <a href={`/certificates/${c.certificate_no}/pdf`} className={buttonStyles("secondary", "sm")}>
                  <Download className="size-4" />{t("cert.download")}
                </a>
              </div>
            </div>
          )}
          {c.completion_message && (
            <Banner tone="gold" icon={<PartyPopper />} title={t("player.course.congrats")} body={c.completion_message} />
          )}
          {c.welcome_message && p.completed === 0 && (
            <Banner tone="brand" icon={<Sparkles />} title={t("player.course.welcome")} body={c.welcome_message} />
          )}
          {!c.has_access && lecture?.unlocked && (
            <p className="rounded-ez border border-gold/40 bg-gold/10 px-4 py-2 text-sm">
              {t("player.course.previewOnly")}{" "}
              <Link href={c.path} className="font-semibold text-brand hover:underline">{t("player.course.getCourse")}</Link>
            </p>
          )}

          {lecture && lecture.unlocked && (
            <>
              <LectureBody lecture={lecture} />
              <div className="flex flex-col gap-4 border-b border-border pb-5 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <p className="text-xs font-bold tracking-[0.12em] text-brand-600 uppercase">{lecture.section_title}</p>
                  <h1 className="font-display text-2xl font-semibold sm:text-3xl">{lecture.title}</h1>
                </div>
                {c.has_access && (
                  lecture.lesson_type === "recorded"
                    ? <p className="max-w-56 text-xs text-muted sm:text-right">{lecture.completed
                        ? <span className="inline-flex items-center gap-1 font-semibold text-success"><CheckCircle2 className="size-4" />{t("player.course.completed")}</span>
                        : t("player.course.autoComplete")}</p>
                    : <CompleteButton courseId={c.id} lectureId={lecture.id} completed={lecture.completed} />
                )}
              </div>
              {lecture.description && <p className="text-[0.9375rem] leading-relaxed whitespace-pre-line text-foreground/85">{lecture.description}</p>}
              <nav className="flex items-center justify-between gap-3">
                {lecture.prev_id ? (
                  <Link href={href(lecture.prev_id)} className={buttonStyles("secondary")}><ArrowLeft className="size-4" />{t("player.course.previous")}</Link>
                ) : <span />}
                {lecture.next_id && (
                  <Link href={href(lecture.next_id)} className={buttonStyles("primary")}>{t("player.course.next")}<ArrowRight className="size-4" /></Link>
                )}
              </nav>
            </>
          )}

          {lecture && !lecture.unlocked && (
            <div className="ez-grain flex aspect-video flex-col items-center justify-center gap-3 rounded-ez-lg bg-brand-900 p-6 text-center text-on-brand">
              <Lock className="size-10 text-gold" />
              <p className="font-display text-2xl font-semibold">{t("player.course.locked")}</p>
              <p className="text-brand-100/80">{t("player.course.lockedBody")}</p>
              <Link href={c.path} className={buttonStyles("gold", "lg")}>{t("player.course.getCourse")}</Link>
            </div>
          )}
        </main>

        <aside className="flex flex-col gap-3 lg:sticky lg:top-20 lg:max-h-[calc(100dvh-6rem)] lg:self-start lg:overflow-y-auto">
          {c.refund && <RefundCard courseId={c.id} info={c.refund} />}
          {askRating && reviewRes?.ok && (
            <RatingCard courseId={c.id} review={reviewRes.data ? { rating: reviewRes.data.rating, comment: reviewRes.data.comment ?? null, status: reviewRes.data.status } : null} />
          )}
          <h2 className="font-display text-xl font-semibold">{t("player.course.content")}</h2>
          <div className="overflow-hidden rounded-ez-lg border border-border bg-surface">
            {c.sections.map((s, si) => {
              const open = s.lectures.some((l) => l.id === currentId) || (si === 0 && !currentId);
              return (
                <details key={s.id} open={open} className="group border-b border-border last:border-b-0">
                  <summary className="flex cursor-pointer list-none items-center gap-2 bg-sunken/60 px-4 py-3 [&::-webkit-details-marker]:hidden">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold">{t("courses.section", { n: si + 1 })}: {s.title}</p>
                      {c.has_access && <p className="text-xs text-muted tabular-nums">{s.completed} / {s.total}</p>}
                    </div>
                    <ChevronDown className="size-4 shrink-0 text-muted transition group-open:rotate-180" aria-hidden />
                  </summary>
                  <ul>
                    {s.lectures.map((l) => {
                      const Icon = icons[l.lesson_type as keyof typeof icons] ?? PlayCircle;
                      const current = l.id === currentId;
                      return (
                        <li key={l.id}>
                          <Link href={href(l.id)} aria-current={current ? "page" : undefined}
                                className={cx("flex items-start gap-3 px-4 py-2.5 text-sm transition hover:bg-sunken/60",
                                              current && "bg-brand-50 font-semibold", !l.unlocked && "text-muted")}>
                            {c.has_access
                              ? l.completed
                                ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-label={t("player.course.completed")} />
                                : <Circle className="mt-0.5 size-4 shrink-0 text-border-strong" aria-hidden />
                              : !l.unlocked && <Lock className="mt-0.5 size-4 shrink-0" aria-hidden />}
                            <span className="min-w-0 flex-1">
                              {l.title}
                              <span className="mt-0.5 flex items-center gap-1 text-xs font-normal text-muted">
                                <Icon className="size-3.5" aria-hidden />
                                {l.video_seconds > 0 ? formatLength(t, l.video_seconds) : t(`courses.type.${l.lesson_type as "article"}`)}
                              </span>
                            </span>
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                </details>
              );
            })}
          </div>
        </aside>
      </Container>
    </SiteShell>
  );
}

function LectureBody({ lecture }: { lecture: Lecture }) {
  // The API types `kind` as a plain string; it is "video" or "document".
  const resources = lecture.resources as StudentResource[];
  const videos = resources.filter((r) => r.kind === "video");
  const files = resources.filter((r) => r.kind !== "video");
  return (
    <div className="flex flex-col gap-5">
      {videos.map((r) => <LectureVideo key={r.id} r={r} />)}
      {lecture.article_body && (
        <article className="rounded-ez-lg border border-border bg-surface p-6 shadow-ez-sm sm:p-8">
          <Markdown text={lecture.article_body} />
        </article>
      )}
      {files.length > 0 && (
        <section className="flex flex-col gap-3 rounded-ez-lg border border-border bg-surface p-4">
          <h2 className="text-sm font-semibold">{t("player.course.resources")}</h2>
          {files.map((r) => <PdfResource key={r.id} r={r} />)}
        </section>
      )}
      {videos.length === 0 && !lecture.article_body && files.length === 0 && (
        <p className="rounded-ez-lg border border-dashed border-border-strong p-6 text-center text-sm text-muted">{t("player.course.noFiles")}</p>
      )}
    </div>
  );
}

function Banner({ tone, icon, title, body }: { tone: "gold" | "brand"; icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className={cx("flex gap-3 rounded-ez-lg border p-4",
                       tone === "gold" ? "border-gold/40 bg-gold/10" : "border-brand/20 bg-brand-50")}>
      <span className={cx("mt-0.5 shrink-0 [&>svg]:size-5", tone === "gold" ? "text-gold-strong" : "text-brand")}>{icon}</span>
      <div>
        <p className="font-semibold">{title}</p>
        <p className="text-sm whitespace-pre-line text-foreground/85">{body}</p>
      </div>
    </div>
  );
}
