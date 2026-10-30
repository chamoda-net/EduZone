import { teachHref } from "@/lib/workspace";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ActionButton } from "@eduzone/ui/action-button";
import { Badge, Card, ClassCover, ErrorText, buttonClass } from "@eduzone/ui";
import { api } from "@/lib/api";
import { classMeta, priceLabel } from "@/lib/catalog";
import { formatDateTime, formatMoney, formatMonth } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import { mediaTone } from "@/lib/media";
import type { ClassItem, ClassStudent, Lesson, LessonResource, MediaPage, Month, SubjectOut } from "@eduzone/lib/types";

import {
  createLesson,
  createMonth,
  deleteClass,
  deleteLesson,
  deleteMonth,
  grantAccess,
  revokeAccess,
  setClassStatus,
  setLessonPublished,
  setMonthStatus,
  updateClass,
  updateLesson,
} from "../actions";
import { ClassForm } from "../class-form";
import { attachFile, removeFile } from "../../media/actions";
import { AddMonthForm, LessonForm } from "./add-forms";
import { AttachFileForm } from "./lesson-files";

export default async function ClassDetailPage({ params, searchParams }: PageProps<"/teach/[tenant]/classes/[id]">) {
  const base = await teachHref();
  const { id } = await params;
  const sp = await searchParams;
  const res = await api<ClassItem>(`~/classes/${id}`);
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    return <ErrorText>{errorText(t, res.error)}</ErrorText>;
  }
  const c = res.data;
  const monthly = c.pricing_model === "monthly";
  const [monthsRes, lessonsRes] = await Promise.all([
    monthly ? api<Month[]>(`~/classes/${id}/months`) : Promise.resolve(null),
    api<Lesson[]>(`~/classes/${id}/lessons`),
  ]);
  const months = monthsRes?.ok ? monthsRes.data : [];
  const lessons = lessonsRes.ok ? lessonsRes.data : [];
  const [mediaRes, ...resourceRes] = await Promise.all([
    api<MediaPage>("~/media?limit=100"),
    ...lessons.map((l) => api<LessonResource[]>(`~/lessons/${l.id}/resources`)),
  ]);
  const media = mediaRes.ok ? (mediaRes.data as MediaPage).items : [];
  const filesByLesson = new Map(
    lessons.map((l, i) => [l.id, resourceRes[i].ok ? (resourceRes[i].data as LessonResource[]) : []]),
  );
  // Students: access is shown for one month at a time (the open month by default).
  const rosterMonth = monthly
    ? (months.find((m) => m.id === sp.month) ?? months.find((m) => m.status === "open") ?? months.at(-1) ?? null)
    : null;
  const rosterRes = monthly && !rosterMonth ? null
    : await api<ClassStudent[]>(`~/classes/${id}/students${rosterMonth ? `?month_id=${rosterMonth.id}` : ""}`);
  const roster = rosterRes?.ok ? rosterRes.data : [];
  const subjectsRes = await api<SubjectOut[]>("/market/subjects", { token: null });
  const subjects = subjectsRes.ok ? subjectsRes.data : [];
  const pricingLocked = c.status !== "draft" || months.length > 0 || lessons.length > 0;

  return (
    <>
      <Link href={`${base}/classes`} className="inline-flex items-center gap-1.5 self-start text-sm font-semibold text-muted hover:text-foreground">
        <ArrowLeft className="size-4" />
        {t("classes.back")}
      </Link>

      <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-5">
          <div className="hidden w-36 shrink-0 overflow-hidden rounded-ez shadow-ez sm:block">
            <ClassCover title={c.title} subject={c.subject} imageUrl={c.cover_image_url} size="sm" />
          </div>
          <div className="flex min-w-0 flex-col gap-1.5">
            <p className="text-xs font-bold tracking-[0.12em] text-brand-600 uppercase">{classMeta(t, c)}</p>
            <h1 className="font-display text-3xl leading-tight font-semibold sm:text-4xl">{c.title}</h1>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
              <Badge tone={c.status} dot>{t(`status.${c.status}`)}</Badge>
              <span>{priceLabel(t, c)}</span>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {c.status === "draft" && (
            <ActionButton action={setClassStatus.bind(null, c.id, "published")} label={t("classDetail.publish")} variant="primary" />
          )}
          {c.status === "published" && (
            <ActionButton action={setClassStatus.bind(null, c.id, "archived")} label={t("classDetail.archive")} />
          )}
          {c.status === "archived" && (
            <ActionButton action={setClassStatus.bind(null, c.id, "published")} label={t("classDetail.republish")} />
          )}
          {c.status === "draft" && (
            <ActionButton
              action={deleteClass.bind(null, c.id)}
              label={t("classDetail.delete")}
              variant="danger"
              confirm={t("classDetail.confirmDelete")}
            />
          )}
        </div>
      </div>

      {monthly && (
        <Card className="flex flex-col gap-4">
          <div>
            <h2 className="font-display text-xl font-semibold">{t("months.title")}</h2>
            <p className="text-xs text-muted">{t("months.closedHint")}</p>
          </div>
          {months.length === 0 ? (
            <p className="text-sm text-muted">{t("months.empty")}</p>
          ) : (
            <ul className="divide-y divide-border">
              {months.map((m) => (
                <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{formatMonth(m.month_start)}</span>
                    <Badge tone={m.status}>{t(`status.${m.status}`)}</Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted">{formatMoney(m.effective_fee_cents, m.currency)}</span>
                    {m.status === "open" ? (
                      <ActionButton action={setMonthStatus.bind(null, c.id, m.id, "closed")} label={t("months.close")} small />
                    ) : (
                      <ActionButton action={setMonthStatus.bind(null, c.id, m.id, "open")} label={t("months.open")} small />
                    )}
                    <ActionButton action={deleteMonth.bind(null, c.id, m.id)} label={t("months.delete")} variant="danger" small />
                  </div>
                </li>
              ))}
            </ul>
          )}
          <AddMonthForm action={createMonth.bind(null, c.id)} suggested={nextMonth(months)} />
        </Card>
      )}

      <Card className="flex flex-col gap-4">
        <h2 className="font-display text-xl font-semibold">{t("lessons.title")}</h2>
        {lessons.length === 0 && <p className="text-sm text-muted">{t("lessons.empty")}</p>}
        {groupLessons(lessons, months, monthly).map((group) => (
          <div key={group.key} className="flex flex-col gap-1">
            {group.label && <h3 className="text-sm font-semibold text-muted">{group.label}</h3>}
            <ul className="divide-y divide-border">
              {group.lessons.map((l) => (
                <li key={l.id} className="flex flex-col gap-2 py-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-medium">
                      {l.title}{" "}
                      {!l.is_published && <Badge tone="draft">{t("lessons.hidden")}</Badge>}
                    </p>
                    <p className="text-sm text-muted">
                      {[
                        t(`lessons.type.${l.lesson_type}`),
                        l.scheduled_at && formatDateTime(l.scheduled_at),
                        l.zoom_join_url && t("lessons.zoomSet"),
                        l.is_free_preview && t("lessons.freePreview"),
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <ActionButton
                      action={setLessonPublished.bind(null, c.id, l.id, !l.is_published)}
                      label={l.is_published ? t("lessons.unpublish") : t("lessons.publish")}
                      small
                    />
                    <ActionButton action={deleteLesson.bind(null, c.id, l.id)} label={t("lessons.delete")} variant="danger" small />
                  </div>
                  </div>
                  <details className="rounded-lg border border-border px-3 py-2 [&[open]]:pb-3">
                    <summary className="cursor-pointer text-sm font-medium text-brand">
                      {t("files.title")} ({filesByLesson.get(l.id)?.length ?? 0})
                    </summary>
                    <div className="flex flex-col gap-3 pt-3">
                      {(filesByLesson.get(l.id) ?? []).length === 0 && (
                        <p className="text-sm text-muted">{t("files.empty")}</p>
                      )}
                      <ul className="flex flex-col gap-1">
                        {(filesByLesson.get(l.id) ?? []).map((f) => (
                          <li key={f.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                            <span className="min-w-0">
                              <Link href={`${base}/media/${f.media.id}`} className={buttonClass.link}>
                                {f.title || f.media.name}
                              </Link>{" "}
                              <span className="text-muted">· {t(`media.kind.${f.media.kind}`)}</span>{" "}
                              {f.media.status !== "ready" && (
                                <Badge tone={mediaTone[f.media.status]}>{t(`media.status.${f.media.status}`)}</Badge>
                              )}{" "}
                              {f.is_downloadable && <Badge tone="upcoming">{t("files.downloadableBadge")}</Badge>}
                            </span>
                            <ActionButton action={removeFile.bind(null, c.id, f.id)} label={t("files.remove")} variant="danger" small />
                          </li>
                        ))}
                      </ul>
                      <AttachFileForm action={attachFile.bind(null, c.id, l.id)} media={media} lessonType={l.lesson_type} />
                    </div>
                  </details>
                  <details className="rounded-lg border border-border px-3 py-2 [&[open]]:pb-3">
                    <summary className="cursor-pointer text-sm font-medium text-brand">{t("lessons.edit")}</summary>
                    <div className="pt-3">
                      <LessonForm
                        action={updateLesson.bind(null, c.id, l.id)}
                        months={months}
                        monthly={monthly}
                        initial={l}
                      />
                    </div>
                  </details>
                </li>
              ))}
            </ul>
          </div>
        ))}
        {monthly && months.length === 0 ? (
          <p className="text-sm text-muted">{t("lessons.noMonthsYet")}</p>
        ) : (
          <LessonForm action={createLesson.bind(null, c.id)} months={months} monthly={monthly} />
        )}
      </Card>

      <Card className="flex flex-col gap-3">
        <h2 className="font-display text-xl font-semibold">{t("students.title")}</h2>
        {monthly && months.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-muted">{t("students.month")}</span>
            {months.map((m) => (
              <Link
                key={m.id}
                href={`${base}/classes/${c.id}?month=${m.id}`}
                scroll={false}
                className={`rounded-full border px-3 py-1 ${m.id === rosterMonth?.id ? "border-brand-800 bg-brand-800 text-on-brand shadow-ez-sm" : "border-border"}`}
              >
                {formatMonth(m.month_start)}
              </Link>
            ))}
          </div>
        )}
        {roster.length === 0 ? (
          <p className="text-sm text-muted">{t("students.empty")}</p>
        ) : (
          <ul className="divide-y divide-border">
            {roster.map((s) => (
              <li key={s.member_id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                <div className="min-w-0">
                  <p className="font-medium">{s.full_name}</p>
                  <p className="text-sm text-muted">
                    {[s.phone, s.enrollment_status === "left" ? t("students.left") : s.enrollment_status === null ? t("students.notJoined") : null]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {s.access ? (
                    <>
                      <Badge tone="published">{t(`students.source.${s.access.source}`)}</Badge>
                      {s.access.source !== "purchase" && (
                        <ActionButton
                          action={revokeAccess.bind(null, c.id, s.access.id)}
                          label={t("students.removeAccess")}
                          variant="danger"
                          small
                          confirm={t("students.confirmRemove")}
                        />
                      )}
                    </>
                  ) : (
                    <>
                      <Badge tone="archived">{t("students.noAccess")}</Badge>
                      <ActionButton
                        action={grantAccess.bind(null, c.id, s.member_id, rosterMonth?.id ?? null, "manual")}
                        label={t("students.giveAccess")}
                        small
                      />
                      <ActionButton
                        action={grantAccess.bind(null, c.id, s.member_id, rosterMonth?.id ?? null, "scholarship")}
                        label={t("students.scholarship")}
                        small
                      />
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="flex flex-col gap-4">
        <h2 className="font-display text-xl font-semibold">{t("classDetail.details")}</h2>
        <ClassForm action={updateClass.bind(null, c.id)} initial={c} subjects={subjects} pricingLocked={pricingLocked} />
      </Card>
    </>
  );
}

function groupLessons(lessons: Lesson[], months: Month[], monthly: boolean) {
  if (!monthly) return [{ key: "all", label: null, lessons }];
  return months
    .map((m) => ({ key: m.id, label: formatMonth(m.month_start), lessons: lessons.filter((l) => l.class_month_id === m.id) }))
    .filter((g) => g.lessons.length > 0);
}

/** The month after the latest one, or the current month (YYYY-MM for <input type="month">). */
function nextMonth(months: Month[]): string {
  const last = months.at(-1)?.month_start;
  const now = new Date();
  const [y, m] = last ? last.split("-").map(Number) : [now.getFullYear(), now.getMonth()];
  const d = new Date(Date.UTC(y, m, 1)); // month m (1-based) as a 0-based index = the next month
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}
