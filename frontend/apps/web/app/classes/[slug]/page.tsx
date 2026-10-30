import { ArrowLeft, ChevronRight, FileText, Lock, MonitorPlay, ShieldCheck, Video } from "lucide-react";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { classMeta, priceParts } from "@/lib/catalog";
import { getMe } from "@/lib/session";
import { formatDateTime, formatMoney, formatMonth } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import type {
  LessonType,
  MonthAccess,
  PublicClassDetail,
  StudentLesson,
  StudentMonth,
} from "@eduzone/lib/types";
import { Avatar, Badge, ClassCover, Container, ErrorText, StatusPill, buttonStyles, cx, type PillState } from "@eduzone/ui";


const pillOf: Record<MonthAccess, PillState> = {
  granted: "paid",
  buy: "unpaid",
  upcoming: "upcoming",
  request: "closed",
  pending: "pending",
  approved: "unpaid",
  rejected: "closed",
  unavailable: "closed",
};

const lessonIcon: Record<LessonType, React.ReactNode> = {
  live: <Video />,
  recorded: <MonitorPlay />,
  document: <FileText />,
};

const shortMonth = new Intl.DateTimeFormat("en", { month: "short", timeZone: "UTC" });

export default async function ClassPage({ params }: PageProps<"/classes/[slug]">) {
  const { slug } = await params;
  const res = await api<PublicClassDetail>(`/public/classes/${encodeURIComponent(slug)}`, { token: null });
  if (!res.ok) {
    if (res.status === 404) notFound();
    return <SiteShell><ErrorText>{errorText(t, res.error)}</ErrorText></SiteShell>;
  }
  // Signed in: the same class, with joining and paying, lives in the student area.
  if (await getMe()) redirect(`/learn/classes/${res.data.class.id}`);
  const view = {
    ...res.data,
    months: res.data.months.map((m) => ({ ...m, access: (m.status === "open" ? "buy" : m.status === "upcoming" ? "upcoming" : "request") as MonthAccess })),
    lessons: res.data.lessons.map((l) => ({ ...l, unlocked: false })),
  };
  const c = view.class;
  const monthly = c.pricing_model === "monthly";
  const price = priceParts(t, c);

  return (
    <SiteShell bare>
      <div className="bg-[linear-gradient(to_bottom,var(--ez-sunken),transparent_520px)]">
        <Container className="grid gap-x-14 gap-y-10 py-8 sm:py-12 lg:grid-cols-[1fr_360px]">
          <div className="flex flex-col gap-5 lg:col-start-1">
            <Link href="/#classes" className="inline-flex items-center gap-1.5 self-start text-sm font-semibold text-muted hover:text-foreground">
              <ArrowLeft className="size-4" />
              {t("nav.browse")}
            </Link>
            <p className="ez-rise text-xs font-bold tracking-[0.14em] text-brand-600 uppercase">{classMeta(t, c)}</p>
            <h1 className="ez-rise font-display text-4xl leading-[1.05] font-semibold sm:text-5xl" style={{ "--i": 1 } as React.CSSProperties}>
              {c.title}
            </h1>
            <div className="ez-rise flex items-center gap-3" style={{ "--i": 2 } as React.CSSProperties}>
              <Avatar name={c.teacher_name} />
              <div>
                <p className="text-xs font-semibold tracking-wide text-muted uppercase">{t("class.teacher")}</p>
                <p className="font-semibold">{c.teacher_name}</p>
              </div>
            </div>
            {c.description && (
              <p className="ez-rise max-w-2xl text-[1.0625rem] leading-relaxed whitespace-pre-line text-foreground/85" style={{ "--i": 3 } as React.CSSProperties}>
                {c.description}
              </p>
            )}
          </div>

          {/* Purchase card: price, the one next step, and trust notes. */}
          <aside className="ez-rise lg:col-start-2 lg:row-span-2 lg:row-start-1" style={{ "--i": 2 } as React.CSSProperties}>
            <div className="overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-lg lg:sticky lg:top-24">
              <ClassCover title={c.title} subject={c.subject} imageUrl={c.cover_image_url} label={c.exam ? t(`exam.${c.exam}`) : null} />
              <div className="flex flex-col gap-4 p-5">
                <p className="flex items-baseline gap-1.5">
                  <span className="font-display text-3xl font-semibold tabular-nums">{price.amount}</span>
                  {price.unit && <span className="text-muted">{price.unit}</span>}
                </p>

                <Link href={`/login?next=/classes/${encodeURIComponent(slug)}`} className={buttonStyles("primary", "lg", "w-full")}>
                  {t("class.signInToJoin")}
                </Link>

                <ul className="flex flex-col gap-2 border-t border-border pt-4 text-sm text-muted">
                  <li className="flex gap-2">
                    <ShieldCheck className="mt-0.5 size-4 shrink-0 text-brand-600" />
                    {t("class.trust.secure")}
                  </li>
                  {monthly && (
                    <li className="flex gap-2">
                      <Lock className="mt-0.5 size-4 shrink-0 text-brand-600" />
                      {t("class.trust.monthly")}
                    </li>
                  )}
                </ul>
              </div>
            </div>
          </aside>

        <div className="flex flex-col gap-12 lg:col-start-1 lg:row-start-2">
          {monthly && view.months.length > 0 && (
            <section className="flex flex-col gap-4">
              <SectionTitle title={t("class.months")} hint={t("class.monthsHint")} />
              <ul className="flex flex-col gap-3">
                {view.months.map((m, i) => (
                  <MonthRow key={m.id} m={m} i={i} />
                ))}
              </ul>
            </section>
          )}

          <section className="flex flex-col gap-4">
            <SectionTitle title={t("class.lessons")} />
            {view.lessons.length === 0 && (
              <p className="rounded-ez-lg border border-dashed border-border-strong p-6 text-center text-sm text-muted">
                {t("class.noLessons")}
              </p>
            )}
            {groupByMonth(view.lessons, view.months, monthly).map((g) => (
              <div key={g.key} className="overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-sm">
                {g.label && (
                  <h3 className="border-b border-border bg-sunken/50 px-5 py-3 text-sm font-bold tracking-wide text-muted">{g.label}</h3>
                )}
                <ul className="divide-y divide-border">
                  {g.lessons.map((l) => (
                    <LessonRow key={l.id} l={l} />
                  ))}
                </ul>
              </div>
            ))}
          </section>

        </div>
        </Container>
      </div>
    </SiteShell>
  );
}

function SectionTitle({ title, hint }: { title: string; hint?: string }) {
  return (
    <div>
      <h2 className="font-display text-2xl font-semibold">{title}</h2>
      {hint && <p className="text-sm text-muted">{hint}</p>}
    </div>
  );
}

function MonthRow({ m, i }: { m: StudentMonth; i: number }) {
  const date = new Date(m.month_start);
  return (
    <li
      className="ez-rise flex flex-wrap items-center gap-4 rounded-ez-lg border border-border bg-surface p-4 shadow-ez-sm sm:flex-nowrap"
      style={{ "--i": i } as React.CSSProperties}
    >
      <div className="grid size-14 shrink-0 place-items-center rounded-ez bg-brand-900 text-center leading-none text-on-brand">
        <span>
          <span className="block text-[0.7rem] font-bold tracking-widest uppercase opacity-80">{shortMonth.format(date)}</span>
          <span className="block font-display text-lg font-semibold">{date.getUTCFullYear()}</span>
        </span>
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{formatMonth(m.month_start)}</p>
        <p className="text-sm text-muted tabular-nums">{formatMoney(m.fee_cents, m.currency)}</p>
      </div>
      <StatusPill state={pillOf[m.access]}>{t(`class.access.${m.access}`)}</StatusPill>
    </li>
  );
}

function LessonRow({ l }: { l: StudentLesson }) {
  const meta = [t(`lessons.type.${l.lesson_type}`), l.scheduled_at && formatDateTime(l.scheduled_at)].filter(Boolean).join(" · ");
  const body = (
    <>
      <span
        className={cx(
          "grid size-10 shrink-0 place-items-center rounded-ez [&>svg]:size-4.5",
          l.unlocked ? "bg-brand-50 text-brand" : "bg-sunken text-subtle",
        )}
      >
        {lessonIcon[l.lesson_type]}
      </span>
      <span className="min-w-0 flex-1">
        <span className={cx("block truncate font-semibold", !l.unlocked && "text-foreground/70")}>{l.title}</span>
        <span className="block text-sm text-muted">{meta}</span>
      </span>
      {l.is_free_preview && <Badge tone="gold">{t("class.freePreview")}</Badge>}
      {l.unlocked ? (
        <ChevronRight className="size-5 shrink-0 text-subtle transition-transform group-hover:translate-x-0.5 group-hover:text-brand" />
      ) : (
        <span className="inline-flex shrink-0 items-center gap-1 text-xs font-semibold text-subtle">
          <Lock className="size-3.5" />
          {t("class.locked")}
        </span>
      )}
    </>
  );
  return (
    <li>
      {l.unlocked ? (
        <Link href={`/learn/lessons/${l.id}`} className="group flex items-center gap-4 px-5 py-4 transition-colors hover:bg-brand-50/50">
          {body}
        </Link>
      ) : (
        <div className="flex items-center gap-4 px-5 py-4">{body}</div>
      )}
    </li>
  );
}

function groupByMonth(lessons: StudentLesson[], months: StudentMonth[], monthly: boolean) {
  if (!monthly) return [{ key: "all", label: null as string | null, lessons }];
  return months
    .map((m) => ({
      key: m.id,
      label: formatMonth(m.month_start) as string | null,
      lessons: lessons.filter((l) => l.class_month_id === m.id),
    }))
    .filter((g) => g.lessons.length > 0);
}
