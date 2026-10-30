import { CalendarDays } from "lucide-react";
import { redirect } from "next/navigation";

import { LessonSlot } from "@/components/lesson-slot";
import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { getMe } from "@/lib/session";
import { errorText, t } from "@eduzone/lib/i18n";
import type { UpcomingLesson } from "@eduzone/lib/types";
import { EmptyState, ErrorText, PageHeader } from "@eduzone/ui";

const dayHeading = new Intl.DateTimeFormat("en", { weekday: "long", day: "numeric", month: "long", timeZone: "Asia/Colombo" });

/** Live classes from every teacher in the next 30 days, grouped by day (Colombo time). */
export default async function SchedulePage() {
  if (!(await getMe())) redirect("/login?next=/learn/schedule");
  const res = await api<UpcomingLesson[]>("/learn/schedule?days=30");

  const days = new Map<string, UpcomingLesson[]>();
  for (const l of res.ok ? res.data : []) {
    const key = dayHeading.format(new Date(l.scheduled_at));
    days.set(key, [...(days.get(key) ?? []), l]);
  }

  return (
    <SiteShell width="md">
      <PageHeader eyebrow={t("learn.eyebrow")} title={t("learn.schedule.title")} description={t("learn.schedule.subtitle")} />
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && days.size === 0 && (
        <EmptyState icon={<CalendarDays />} title={t("learn.schedule.empty")} body={t("learn.schedule.emptyBody")} />
      )}
      {[...days].map(([day, lessons]) => (
        <section key={day} className="flex flex-col gap-3">
          <h2 className="text-sm font-bold tracking-wide text-muted uppercase">{day}</h2>
          <ul className="flex flex-col gap-3">
            {lessons.map((l, i) => <LessonSlot key={l.lesson_id} l={l} i={i} />)}
          </ul>
        </section>
      ))}
    </SiteShell>
  );
}
