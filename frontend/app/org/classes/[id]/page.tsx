import Link from "next/link";
import { notFound } from "next/navigation";

import { ActionButton } from "@/components/action-button";
import { Badge, Card, ErrorText, buttonClass } from "@/components/ui";
import { api } from "@/lib/api";
import { classMeta, priceLabel } from "@/lib/catalog";
import { formatDateTime, formatMoney, formatMonth } from "@/lib/format";
import { errorText, t } from "@/lib/i18n";
import type { ClassItem, Lesson, Month } from "@/lib/types";

import {
  createLesson,
  createMonth,
  deleteClass,
  deleteLesson,
  deleteMonth,
  setClassStatus,
  setLessonPublished,
  setMonthStatus,
  updateClass,
} from "../actions";
import { ClassForm } from "../class-form";
import { AddLessonForm, AddMonthForm } from "./add-forms";

export default async function ClassDetailPage({ params }: PageProps<"/org/classes/[id]">) {
  const { id } = await params;
  const res = await api<ClassItem>(`/org/classes/${id}`);
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    return <ErrorText>{errorText(t, res.error)}</ErrorText>;
  }
  const c = res.data;
  const monthly = c.pricing_model === "monthly";
  const [monthsRes, lessonsRes] = await Promise.all([
    monthly ? api<Month[]>(`/org/classes/${id}/months`) : Promise.resolve(null),
    api<Lesson[]>(`/org/classes/${id}/lessons`),
  ]);
  const months = monthsRes?.ok ? monthsRes.data : [];
  const lessons = lessonsRes.ok ? lessonsRes.data : [];
  const pricingLocked = c.status !== "draft" || months.length > 0 || lessons.length > 0;

  return (
    <>
      <Link href="/org/classes" className={`${buttonClass.link} text-sm`}>← {t("classes.back")}</Link>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold">{c.title}</h1>
            <Badge tone={c.status}>{t(`status.${c.status}`)}</Badge>
          </div>
          <p className="text-sm text-muted">{[classMeta(t, c), priceLabel(t, c)].filter(Boolean).join(" · ")}</p>
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
            <h2 className="text-lg font-semibold">{t("months.title")}</h2>
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
        <h2 className="text-lg font-semibold">{t("lessons.title")}</h2>
        {lessons.length === 0 && <p className="text-sm text-muted">{t("lessons.empty")}</p>}
        {groupLessons(lessons, months, monthly).map((group) => (
          <div key={group.key} className="flex flex-col gap-1">
            {group.label && <h3 className="text-sm font-semibold text-muted">{group.label}</h3>}
            <ul className="divide-y divide-border">
              {group.lessons.map((l) => (
                <li key={l.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
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
                </li>
              ))}
            </ul>
          </div>
        ))}
        {monthly && months.length === 0 ? (
          <p className="text-sm text-muted">{t("lessons.noMonthsYet")}</p>
        ) : (
          <AddLessonForm action={createLesson.bind(null, c.id)} months={months} monthly={monthly} />
        )}
      </Card>

      <Card className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold">{t("classDetail.details")}</h2>
        <ClassForm action={updateClass.bind(null, c.id)} initial={c} pricingLocked={pricingLocked} />
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
