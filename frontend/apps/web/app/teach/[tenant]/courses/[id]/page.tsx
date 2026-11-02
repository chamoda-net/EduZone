import { AlertTriangle, ArrowDown, ArrowLeft, ArrowUp, CheckCircle2, Circle, Clock, Eye, EyeOff, FileText, Globe2,
  PlayCircle, ScrollText } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import type { Schema } from "@eduzone/api-client";
import { api } from "@/lib/api";
import { mediaTone } from "@/lib/media";
import { teachHref } from "@/lib/workspace";
import { formatMoney } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import type { LessonResource, MediaPage } from "@eduzone/lib/types";
import { ActionButton } from "@eduzone/ui/action-button";
import { Badge, Card, ClassCover, ErrorText, buttonClass, cx } from "@eduzone/ui";

import {
  addLecture, addSection, attachLectureFile, courseAction, deleteCourse, deleteLecture, deleteSection, removeLectureFile,
  renameSection, saveLanding, saveLearners, saveLecture, saveMessages, savePricing, swapLectures, swapSections,
} from "../actions";
import { InlineForm, LandingForm, LearnersForm, LectureForm, LectureTypeSelect, MessagesForm, PricingForm } from "../forms";
import { AttachFileForm } from "../../classes/[id]/lesson-files";

type CourseDetail = Schema<"CourseDetail">;
type Category = Schema<"CategoryOut">;
type Check = Schema<"Check">;

const TABS = ["landing", "learners", "curriculum", "pricing", "messages"] as const;
type Tab = (typeof TABS)[number];

// Which tab fixes which check.
const CHECK_TAB: Record<string, Tab | null> = {
  tenant_approved: null, subtitle: "landing", description: "landing", cover: "landing", category: "landing",
  level: "landing", language: "landing", objectives: "learners", requirements: "learners", audience: "learners",
  price: "pricing", lectures: "curriculum", video_minutes: "curriculum", videos_ready: "curriculum",
  instructor_profile: null,
};
const statusTone = { draft: "draft", in_review: "upcoming", published: "published", archived: "archived" } as const;

function checkText(c: Check): string {
  const key = `courses.check.${c.key}` as Parameters<typeof t>[0];
  return t(key, { current: c.current ?? 0, required: c.required ?? 0 });
}

const lectureIcon = { recorded: PlayCircle, document: FileText, article: ScrollText } as const;

export default async function CourseBuilderPage({ params, searchParams }: PageProps<"/teach/[tenant]/courses/[id]">) {
  const base = await teachHref();
  const { id } = await params;
  const sp = await searchParams;
  const tab: Tab = TABS.includes(sp.tab as Tab) ? (sp.tab as Tab) : "landing";
  const res = await api<CourseDetail>(`~/courses/${id}`);
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    return <ErrorText>{errorText(t, res.error)}</ErrorText>;
  }
  const c = res.data;
  const [categoriesRes, mediaRes] = await Promise.all([
    api<Category[]>("/market/course-categories", { token: null }),
    api<MediaPage>("~/media?limit=100"),
  ]);
  const categories = categoriesRes.ok ? categoriesRes.data : [];
  const media = mediaRes.ok ? mediaRes.data.items : [];
  const lectures = c.sections.flatMap((s) => s.lectures);
  const files = tab === "curriculum"
    ? new Map(await Promise.all(lectures.map(async (l) => {
        const r = await api<LessonResource[]>(`~/lessons/${l.id}/resources`);
        return [l.id, r.ok ? r.data : []] as const;
      })))
    : new Map<string, LessonResource[]>();
  const done = c.checks.filter((x) => x.ok).length;
  const locked = c.status === "in_review";
  const minutes = Math.round(c.total_video_seconds / 60);

  return (
    <>
      <Link href={`${base}/courses`} className="inline-flex items-center gap-1.5 self-start text-sm font-semibold text-muted hover:text-foreground">
        <ArrowLeft className="size-4" />
        {t("courses.back")}
      </Link>

      <header className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 items-center gap-5">
          <div className="hidden w-40 shrink-0 overflow-hidden rounded-ez shadow-ez sm:block">
            <ClassCover title={c.title} subject={null} imageUrl={c.cover_image_url} size="sm" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={statusTone[c.status as keyof typeof statusTone]} dot>
                {t(`status.${c.status as keyof typeof statusTone}`)}
              </Badge>
              <span className="text-xs text-muted">
                {t("courses.totalLength", { lectures: t("courses.lectures", { count: c.lecture_count }), minutes })}
                {" · "}
                {c.pricing_model === "free" || !c.one_time_price_cents ? t("courses.pricingFree")
                  : formatMoney(c.one_time_price_cents, c.currency)}
              </span>
            </div>
            <h1 className="mt-1 font-display text-3xl leading-tight font-semibold">{c.title}</h1>
            <p className="font-mono text-xs text-muted">/course/{c.slug}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-start gap-2">
          {(c.status === "draft" || c.status === "archived") && (
            <ActionButton variant="primary" action={courseAction.bind(null, c.id, "submit")}
                          label={c.needs_review ? t("courses.submit") : t("courses.publishAgain")}
                          done={c.needs_review ? t("courses.submitted") : t("courses.saved")} />
          )}
          {c.status === "in_review" && (
            <ActionButton action={courseAction.bind(null, c.id, "withdraw")} label={t("courses.withdraw")} />
          )}
          {c.status === "published" && (
            <ActionButton action={courseAction.bind(null, c.id, "unpublish")} label={t("courses.unpublish")}
                          confirm={t("courses.confirmUnpublish")} />
          )}
          {c.status === "draft" && c.first_published_at === null && (
            <ActionButton variant="ghost" action={deleteCourse.bind(null, c.id)} label={t("courses.delete")}
                          confirm={t("courses.confirmDelete")} />
          )}
        </div>
      </header>

      {c.status === "in_review" && (
        <Banner tone="info" icon={<Clock />} title={t("courses.inReviewTitle")} body={t("courses.inReviewBody")} />
      )}
      {c.status === "published" && (
        <Banner tone="success" icon={<Globe2 />} title={t("courses.liveTitle")} body={t("courses.liveBody")} />
      )}
      {c.review_note && c.status !== "published" && c.status !== "in_review" && (
        <Banner tone="warning" icon={<AlertTriangle />}
                title={c.status === "archived" ? t("courses.unpublishedTitle") : t("courses.changesTitle")}
                body={`${t("courses.reviewNoteFrom")}: ${c.review_note}`} />
      )}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex min-w-0 flex-col gap-4">
          <nav aria-label={t("courses.title")} className="-mx-4 flex gap-1 overflow-x-auto border-b border-border px-4 [scrollbar-width:none] sm:mx-0 sm:px-0">
            {TABS.map((x) => (
              <Link key={x} href={`${base}/courses/${c.id}?tab=${x}`} aria-current={x === tab ? "page" : undefined}
                    className={cx(
                      "-mb-px shrink-0 border-b-2 px-3 py-2.5 text-sm font-semibold whitespace-nowrap transition-colors",
                      x === tab ? "border-brand text-foreground" : "border-transparent text-muted hover:text-foreground",
                    )}>
                {t(`courses.tab.${x}`)}
              </Link>
            ))}
          </nav>

          <fieldset disabled={locked} className="contents">
            {tab === "landing" && (
              <Card><LandingForm action={saveLanding.bind(null, c.id)} course={c} categories={categories} media={media} /></Card>
            )}
            {tab === "learners" && <Card><LearnersForm action={saveLearners.bind(null, c.id)} course={c} /></Card>}
            {tab === "pricing" && <Card><PricingForm action={savePricing.bind(null, c.id)} course={c} /></Card>}
            {tab === "messages" && <Card><MessagesForm action={saveMessages.bind(null, c.id)} course={c} /></Card>}
          </fieldset>

          {tab === "curriculum" && (
            <div className="flex flex-col gap-4">
              {c.sections.length === 0 && <p className="text-sm text-muted">{t("courses.noSections")}</p>}
              {c.sections.map((s, si) => (
                <section key={s.id} className="overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-sm">
                  <div className="flex flex-col gap-2 border-b border-border bg-sunken/50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                    <p className="font-display text-lg font-semibold">
                      <span className="mr-2 text-sm font-bold tracking-wide text-brand-600 uppercase">{t("courses.section", { n: si + 1 })}</span>
                      {s.title}
                    </p>
                    {!locked && (
                      <div className="flex flex-wrap items-center gap-1">
                        {si > 0 && (
                          <IconAction label={t("courses.moveUp")} icon={<ArrowUp />}
                                      action={swapSections.bind(null, c.id, s.id, si, c.sections[si - 1].id, si - 1)} />
                        )}
                        {si < c.sections.length - 1 && (
                          <IconAction label={t("courses.moveDown")} icon={<ArrowDown />}
                                      action={swapSections.bind(null, c.id, s.id, si, c.sections[si + 1].id, si + 1)} />
                        )}
                        {s.lectures.length === 0 && (
                          <ActionButton small variant="ghost" action={deleteSection.bind(null, c.id, s.id)} label={t("courses.deleteSection")} />
                        )}
                      </div>
                    )}
                  </div>

                  <ul className="divide-y divide-border">
                    {s.lectures.length === 0 && <li className="px-4 py-3 text-sm text-muted">{t("courses.noLectures")}</li>}
                    {s.lectures.map((l, li) => {
                      const Icon = lectureIcon[l.lesson_type as keyof typeof lectureIcon] ?? PlayCircle;
                      const lectureFiles = files.get(l.id) ?? [];
                      return (
                        <li key={l.id} className="flex flex-col gap-2 px-4 py-3">
                          <div className="flex flex-wrap items-center gap-3">
                            <Icon className="size-5 shrink-0 text-brand-600" aria-hidden />
                            <div className="min-w-0 flex-1">
                              <p className={cx("font-medium", !l.is_published && "text-muted")}>{l.title}</p>
                              <p className="flex flex-wrap items-center gap-x-2 text-xs text-muted">
                                <span>{t(`courses.type.${l.lesson_type as "recorded"}`)}</span>
                                {l.video_seconds > 0 && <span>· {t("courses.minutes", { count: Math.round(l.video_seconds / 60) })}</span>}
                                {l.pending_videos > 0 && <span className="text-warning">· {t("courses.processing")}</span>}
                              </p>
                            </div>
                            {l.is_free_preview && <Badge tone="gold"><Eye className="size-3" />{t("courses.preview")}</Badge>}
                            {!l.is_published && <Badge tone="neutral"><EyeOff className="size-3" />{t("courses.hidden")}</Badge>}
                            {!locked && (
                              <div className="flex items-center gap-1">
                                {li > 0 && (
                                  <IconAction label={t("courses.moveUp")} icon={<ArrowUp />}
                                              action={swapLectures.bind(null, c.id, l.id, li, s.lectures[li - 1].id, li - 1)} />
                                )}
                                {li < s.lectures.length - 1 && (
                                  <IconAction label={t("courses.moveDown")} icon={<ArrowDown />}
                                              action={swapLectures.bind(null, c.id, l.id, li, s.lectures[li + 1].id, li + 1)} />
                                )}
                              </div>
                            )}
                          </div>
                          {!locked && (
                            <div className="flex flex-col gap-2 pl-8">
                              <details className="rounded-ez border border-border px-3 py-2 [&[open]]:pb-3">
                                <summary className="cursor-pointer text-sm font-medium text-brand">{t("courses.editLecture")}</summary>
                                <div className="pt-3"><LectureForm action={saveLecture.bind(null, c.id, l.id)} lecture={l} /></div>
                              </details>
                              {l.lesson_type !== "article" || lectureFiles.length > 0 ? (
                                <details className="rounded-ez border border-border px-3 py-2 [&[open]]:pb-3">
                                  <summary className="cursor-pointer text-sm font-medium text-brand">
                                    {t("courses.files", { count: lectureFiles.length })}
                                  </summary>
                                  <div className="flex flex-col gap-3 pt-3">
                                    {lectureFiles.length === 0 && <p className="text-sm text-muted">{t("files.empty")}</p>}
                                    <ul className="flex flex-col gap-1">
                                      {lectureFiles.map((f) => (
                                        <li key={f.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                                          <span className="min-w-0">
                                            <Link href={`${base}/media/${f.media.id}`} className={buttonClass.link}>{f.title || f.media.name}</Link>{" "}
                                            <span className="text-muted">· {t(`media.kind.${f.media.kind}`)}</span>{" "}
                                            {f.media.status !== "ready" && (
                                              <Badge tone={mediaTone[f.media.status]}>{t(`media.status.${f.media.status}`)}</Badge>
                                            )}
                                          </span>
                                          <ActionButton action={removeLectureFile.bind(null, c.id, f.id)} label={t("files.remove")} variant="danger" small />
                                        </li>
                                      ))}
                                    </ul>
                                    <AttachFileForm action={attachLectureFile.bind(null, c.id, l.id)} media={media}
                                                    lessonType={l.lesson_type === "recorded" ? "recorded" : "document"} />
                                  </div>
                                </details>
                              ) : null}
                              {(c.first_published_at === null || !l.is_published) && (
                                <div className="self-start">
                                  <ActionButton small variant="ghost" action={deleteLecture.bind(null, c.id, l.id)}
                                                label={t("courses.deleteLecture")} confirm={t("courses.confirmDeleteLecture")} />
                                </div>
                              )}
                            </div>
                          )}
                        </li>
                      );
                    })}
                  </ul>

                  {!locked && (
                    <div className="border-t border-dashed border-border px-4 py-3">
                      <InlineForm action={addLecture.bind(null, c.id, s.id)} name="title" label={t("courses.lectureTitle")}
                                  placeholder={t("courses.lectureTitle")} button={t("courses.addLecture")}>
                        <LectureTypeSelect />
                      </InlineForm>
                    </div>
                  )}
                  {!locked && (
                    <details className="border-t border-border px-4 py-2 text-sm [&[open]]:pb-3">
                      <summary className="cursor-pointer font-medium text-muted hover:text-foreground">{t("courses.renameSection")}</summary>
                      <div className="pt-2">
                        <InlineForm action={renameSection.bind(null, c.id, s.id)} name="title" label={t("courses.sectionTitle")}
                                    initial={s.title} button={t("courses.save")} />
                      </div>
                    </details>
                  )}
                </section>
              ))}
              {!locked && (
                <Card className="border-dashed">
                  <p className="mb-2 font-semibold">{t("courses.addSection")}</p>
                  <InlineForm action={addSection.bind(null, c.id)} name="title" label={t("courses.sectionTitle")}
                              placeholder={t("courses.sectionPlaceholder")} button={t("courses.addSection")} />
                </Card>
              )}
            </div>
          )}
        </div>

        <aside className="flex flex-col gap-4 lg:sticky lg:top-6">
          <Card className="flex flex-col gap-3">
            <div className="flex items-baseline justify-between gap-2">
              <h2 className="font-display text-lg font-semibold">{t("courses.checklist")}</h2>
              <span className="text-xs text-muted tabular-nums">{t("courses.checklistDone", { done, total: c.checks.length })}</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-sunken" aria-hidden>
              <div className="h-full rounded-full bg-brand transition-all" style={{ width: `${(done / c.checks.length) * 100}%` }} />
            </div>
            <ul className="flex flex-col gap-2 text-sm">
              {c.checks.map((x) => {
                const target = CHECK_TAB[x.key];
                const label = checkText(x);
                return (
                  <li key={x.key} className="flex gap-2">
                    {x.ok ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-label="✓" />
                      : <Circle className="mt-0.5 size-4 shrink-0 text-border-strong" aria-label="○" />}
                    {!x.ok && target ? (
                      <Link href={`${base}/courses/${c.id}?tab=${target}`} className="text-foreground hover:text-brand hover:underline">{label}</Link>
                    ) : !x.ok && x.key === "instructor_profile" ? (
                      <Link href={`${base}/profile`} className="text-foreground hover:text-brand hover:underline">{label}</Link>
                    ) : (
                      <span className={x.ok ? "text-muted" : ""}>{label}</span>
                    )}
                  </li>
                );
              })}
            </ul>
            {c.needs_review && <p className="border-t border-border pt-3 text-xs text-muted">{t("courses.submitHint")}</p>}
          </Card>
        </aside>
      </div>
    </>
  );
}

function Banner({ tone, icon, title, body }: { tone: "info" | "success" | "warning"; icon: React.ReactNode; title: string; body: string }) {
  const tones = {
    info: "border-info/25 bg-info-bg text-info",
    success: "border-success/25 bg-success-bg text-success",
    warning: "border-warning/25 bg-warning-bg text-warning",
  };
  return (
    <div role="status" className={cx("flex gap-3 rounded-ez-lg border p-4", tones[tone])}>
      <span className="mt-0.5 shrink-0 [&>svg]:size-5">{icon}</span>
      <div>
        <p className="font-semibold">{title}</p>
        <p className="text-sm text-foreground/80">{body}</p>
      </div>
    </div>
  );
}

/** A small icon button that runs a server action (move up/down). */
function IconAction({ label, icon, action }: { label: string; icon: React.ReactNode; action: () => Promise<void> }) {
  return (
    <form action={action}>
      <button aria-label={label} title={label}
              className="grid size-8 place-items-center rounded-ez text-muted hover:bg-sunken hover:text-foreground [&>svg]:size-4">
        {icon}
      </button>
    </form>
  );
}
