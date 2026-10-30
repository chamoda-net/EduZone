import { BookOpen, CalendarDays, CalendarX2, CircleCheck, Hourglass } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { LessonSlot } from "@/components/lesson-slot";
import { PayButton } from "@/components/pay-button";
import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { getMe } from "@/lib/session";
import { formatMoney, formatMonth } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import type { Today } from "@eduzone/lib/types";
import { Badge, CardTitle, EmptyState, ErrorText, PageHeader, buttonStyles } from "@eduzone/ui";

/** Today: the next live class from any teacher, what is waiting to be paid, and requests. */
export default async function TodayPage() {
  const me = await getMe();
  if (!me) redirect("/login?next=/learn");
  const res = await api<Today>("/learn/today");
  const first = me.full_name.split(/\s+/)[0];

  return (
    <SiteShell>
      <PageHeader
        eyebrow={t("learn.eyebrow")}
        title={t("learn.today.greeting", { name: first })}
        description={t("learn.today.subtitle")}
        actions={
          <Link href="/learn/classes" className={buttonStyles("secondary")}>
            <BookOpen className="size-4.5" />
            {res.ok ? t("learn.today.classes", { count: res.data.classes }) : t("nav.myClasses")}
          </Link>
        }
      />
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.classes === 0 && (
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
                    <PayButton block classId={m.class_id} monthId={m.month_id}
                               label={t("pay.button", { amount: formatMoney(m.fee_cents, m.currency) })} />
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
