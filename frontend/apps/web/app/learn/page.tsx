import { Armchair, ArrowRight, BookOpen, CalendarDays, CalendarX2, CircleCheck, GraduationCap, Hourglass } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import type { Schema } from "@eduzone/api-client";
import { Lane } from "@/components/lane";
import { LessonSlot } from "@/components/lesson-slot";
import { MyCourseCard } from "@/components/my-course-card";
import { PayButton } from "@/components/pay-button";
import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { deadline } from "@/lib/seats";
import { getMe } from "@/lib/session";
import { formatMoney, formatMonth } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import type { Today } from "@eduzone/lib/types";
import { Badge, CardTitle, EmptyState, ErrorText, PageHeader, buttonStyles } from "@eduzone/ui";

/** Today: the next live class from any teacher, what is waiting to be paid, and requests. */
export default async function TodayPage() {
  const me = await getMe();
  if (!me) redirect("/login?next=/learn");
  const [res, coursesRes, requestsRes, waitsRes] = await Promise.all([
    api<Today>("/learn/today"),
    api<Schema<"MyCourse">[]>("/learn/courses"),
    api<Schema<"MySeatRequestRow">[]>("/learn/seat-requests"),
    api<Schema<"MySeatWait">[]>("/learn/seat-waits"),
  ]);
  // Seats worth acting on now: accepted requests to pay for, and classes where one opened.
  const accepted = requestsRes.ok ? requestsRes.data.filter((r) => r.status === "approved") : [];
  const opened = waitsRes.ok ? waitsRes.data.filter((w) => w.available) : [];
  const courses = coursesRes.ok ? coursesRes.data : [];
  const first = me.full_name.split(/\s+/)[0];

  return (
    <SiteShell>
      <PageHeader
        eyebrow={t("learn.eyebrow")}
        title={t("learn.today.greeting", { name: first })}
        description={t("learn.today.subtitle")}
        actions={
          <>
            <Link href="/learn/courses" className={buttonStyles("secondary")}>
              <GraduationCap className="size-4.5" />
              {t("nav.myCourses")}
            </Link>
            <Link href="/learn/classes" className={buttonStyles("secondary")}>
              <BookOpen className="size-4.5" />
              {res.ok ? t("learn.today.classes", { count: res.data.classes }) : t("nav.myClasses")}
            </Link>
          </>
        }
      />
      {courses.length > 0 && (
        <section className="flex flex-col gap-4">
          <CardTitle action={<Link href="/learn/courses" className="text-sm font-semibold text-brand hover:underline">{t("learnCourses.seeAll")}</Link>}>
            {t("learnCourses.continueLane")}
          </CardTitle>
          <Lane label={t("learnCourses.continueLane")}>
            {courses.slice(0, 4).map((c, i) => <MyCourseCard key={c.id} c={c} index={i} />)}
          </Lane>
        </section>
      )}
      {accepted.length + opened.length > 0 && (
        <section className="flex flex-col gap-3" aria-label={t("seat.today.title")}>
          {accepted.map((r) => (
            <SeatBanner key={r.id} href={`/learn/classes/${r.class_id}`} title={t("seat.today.accepted", { title: r.class_title })}
                        body={r.held_until ? t("seat.payBy", { when: deadline(r.held_until) }) : r.org.name} />
          ))}
          {opened.map((w) => (
            <SeatBanner key={w.class_id} href={`/learn/classes/${w.class_id}`} body={w.org.name}
                        title={t(w.needs_request ? "seat.today.openedAsk" : "seat.today.opened", { title: w.class_title })} />
          ))}
        </section>
      )}
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.classes === 0 && courses.length === 0 && (
        <EmptyState icon={<BookOpen />} title={t("my.empty")} body={t("my.emptyBody")} />
      )}
      {res.ok && res.data.classes > 0 && (
        <div className="grid gap-10 lg:grid-cols-[1.4fr_1fr]">
          <section className="flex min-w-0 flex-col gap-4">
            <CardTitle
              action={<Link href="/learn/schedule" className="text-sm font-semibold text-brand hover:underline">{t("nav.schedule")}</Link>}
            >
              {t("learn.today.next")}
            </CardTitle>
            {res.data.next_live.length === 0 ? (
              <p className="flex items-center gap-3 rounded-ez-lg border border-dashed border-border-strong p-5 text-sm text-muted">
                <CalendarX2 className="size-5 text-subtle" />
                {t("learn.today.noLive")}
              </p>
            ) : (
              <ul className="flex flex-col gap-3">
                {res.data.next_live.map((l, i) => <LessonSlot key={l.lesson_id} l={l} i={i} />)}
              </ul>
            )}
          </section>

          <section className="flex min-w-0 flex-col gap-4">
            <CardTitle>{t("learn.today.toPay")}</CardTitle>
            {res.data.pending_requests > 0 && (
              <Link href="/learn/requests" className="flex items-center gap-3 rounded-ez border border-warning/25 bg-warning-bg px-4 py-3 text-sm font-medium text-warning hover:underline">
                <Hourglass className="size-4.5 shrink-0" />
                {t("learn.today.requests", { count: res.data.pending_requests })}
              </Link>
            )}
            {res.data.to_pay.length === 0 ? (
              <p className="flex items-center gap-3 rounded-ez-lg border border-success/25 bg-success-bg p-5 text-sm font-medium text-success">
                <CircleCheck className="size-5" />
                {t("learn.today.allPaid")}
              </p>
            ) : (
              <ul className="flex flex-col gap-3">
                {res.data.to_pay.map((m, i) => (
                  <li
                    key={m.month_id}
                    className="ez-rise flex flex-col gap-3 rounded-ez-lg border border-gold/30 bg-surface p-4 shadow-ez-sm"
                    style={{ "--i": i } as React.CSSProperties}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <Link href={`/learn/classes/${m.class_id}`} className="min-w-0 hover:underline">
                        <p className="truncate font-semibold">{m.class_title}</p>
                        <p className="truncate text-sm text-muted">{m.org.name}</p>
                      </Link>
                      <Badge tone="gold" dot>
                        <CalendarDays className="size-3" />
                        {formatMonth(m.month_start)}
                      </Badge>
                    </div>
                    {m.approved_late && <p className="text-xs font-medium text-info">{t("learn.today.pastMonth")}</p>}
                    {m.seat?.kept_until && <p className="flex gap-2 text-sm font-medium text-success"><Armchair className="mt-0.5 size-4 shrink-0" />{t("seat.kept", { when: deadline(m.seat.kept_until) })}</p>}
                    {m.seat?.problem ? (
                      <>
                        <p className="text-sm text-muted">{t(`errors.${m.seat.problem}`)}</p>
                        <Link href={`/learn/classes/${m.class_id}`} className={buttonStyles("secondary", "md", "w-full")}>{t("seat.today.go")}</Link>
                      </>
                    ) : (
                      <PayButton block classId={m.class_id} monthId={m.month_id}
                                 label={t("pay.button", { amount: formatMoney(m.fee_cents, m.currency) })} />
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </SiteShell>
  );
}

function SeatBanner({ href, title, body }: { href: string; title: string; body: string }) {
  return (
    <Link href={href} className="ez-rise group flex items-center gap-4 rounded-ez-lg border border-gold/40 bg-gold-100/60 p-4 shadow-ez-sm hover:border-gold">
      <span className="grid size-11 shrink-0 place-items-center rounded-full bg-gold text-brand-950"><Armchair className="size-5" /></span>
      <span className="min-w-0 flex-1">
        <span className="block font-semibold">{title}</span>
        <span className="block text-sm text-muted">{body}</span>
      </span>
      <ArrowRight className="size-5 shrink-0 text-brand transition group-hover:translate-x-0.5" />
    </Link>
  );
}
