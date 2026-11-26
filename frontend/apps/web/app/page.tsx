import { ArrowRight, CalendarCheck, Check, ChevronDown, CreditCard, FileText, GraduationCap, MonitorPlay, PlayCircle, Radio, Search, ShieldCheck, Sparkles } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import type { Schema } from "@eduzone/api-client";
import { CourseCard } from "@/components/course-card";
import { Lane } from "@/components/lane";
import { MarketClassCard } from "@/components/market-card";
import { Photo } from "@/components/photo";
import { SiteShell } from "@/components/shell";
import { SubjectTile } from "@/components/subject-tile";
import { api, userHost } from "@/lib/api";
import { PHOTOS } from "@/lib/photos";
import { isMainHost, mainOrigin } from "@/lib/site";
import { OG_BASE } from "@/lib/seo";
import { errorText, t } from "@eduzone/lib/i18n";
import type { MarketClass, MarketHome } from "@eduzone/lib/types";
import { Container, ErrorText, buttonStyles } from "@eduzone/ui";

const FAQ = ["pay", "join", "missed", "phone", "devices", "courses"] as const;
// The live totals strip shows once the numbers inspire confidence; below these, no numbers at all.
const STATS_MIN_CLASSES = 20;
const STATS_MIN_TEACHERS = 10;

export const metadata: Metadata = {
  title: { absolute: t("home.meta.title") },
  description: t("home.meta.description"),
  alternates: { canonical: "/" },
  openGraph: { ...OG_BASE, title: t("home.meta.title"), description: t("home.meta.description"), url: "/" },
};

/** The marketplace home. A tenant's old subdomain now points to its classes on the main site. */
export default async function Home() {
  if (!(await isMainHost())) {
    const slug = (await userHost()).split(".")[0];
    redirect(`${await mainOrigin()}/classes?org=${encodeURIComponent(slug)}`);
  }
  const [res, coursesRes] = await Promise.all([
    api<MarketHome>("/market/home", { token: null }),
    api<Schema<"CoursesHome">>("/market/courses/home", { token: null }),
  ]);
  const courses = coursesRes.ok ? coursesRes.data : null;
  const data = res.ok ? res.data : null;

  return (
    <SiteShell bare>
      <Hero data={data} />

      {!res.ok && <Container className="py-10"><ErrorText>{errorText(t, res.error)}</ErrorText></Container>}

      <HowItWorks />

      {data && (
        <>
          <Container className="flex flex-col gap-6 pt-16 sm:pt-24">
            <SectionHead eyebrow={t("market.home.subjectsEyebrow")} title={t("market.home.subjects")} href="/classes" />
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-4">
              {data.subjects.filter((s) => s.class_count > 0).concat(data.subjects.filter((s) => s.class_count === 0))
                .slice(0, 8).map((s, i) => <SubjectTile key={s.slug} s={s} i={i} />)}
            </ul>
          </Container>

          {data.starting.length > 0 && (
            <ClassRow eyebrow={t("market.home.startingEyebrow")} title={t("market.home.starting")} classes={data.starting} />
          )}
          <ClassRow eyebrow={t("market.home.popularEyebrow")} title={t("market.home.popular")} classes={data.popular} />

          <Results data={data} />

          {courses && courses.total > 0 && (
            <Container className="flex flex-col gap-6 pt-16 sm:pt-24">
              <SectionHead eyebrow={t("market.home.coursesEyebrow")} title={t("market.home.courses")} href="/courses" />
              <p className="-mt-3 max-w-2xl text-muted">{t("market.home.coursesBody")}</p>
              {courses.categories.filter((c) => c.course_count > 0).length > 0 && (
                <nav aria-label={t("market.home.courseCategories")} className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 [scrollbar-width:none] sm:mx-0 sm:px-0">
                  {courses.categories.filter((c) => c.course_count > 0).map((c) => (
                    <Link key={c.slug} href={`/courses/${c.slug}`}
                          className="inline-flex min-h-10 shrink-0 items-center gap-2 rounded-full border border-border-strong bg-surface px-4 text-sm font-semibold whitespace-nowrap text-muted transition hover:border-foreground/40 hover:text-foreground">
                      {c.name_en}
                      <span className="rounded-full bg-sunken px-1.5 text-xs tabular-nums">{c.course_count}</span>
                    </Link>
                  ))}
                </nav>
              )}
              <Lane label={t("market.home.courses")}>
                {courses.popular.slice(0, 8).map((c, i) => <CourseCard key={c.id} c={c} index={i} />)}
              </Lane>
            </Container>
          )}
        </>
      )}

      <TeachBand />
      <Faq />
    </SiteShell>
  );
}

function showStats(data: MarketHome): boolean {
  return data.classes >= STATS_MIN_CLASSES && data.teachers >= STATS_MIN_TEACHERS;
}

function SectionHead({ eyebrow, title, href, body }: { eyebrow: string; title: string; href?: string; body?: string }) {
  return (
    <div className="flex items-end justify-between gap-4">
      <div className="flex max-w-2xl flex-col gap-1">
        <p className="text-xs font-bold tracking-[0.14em] text-brand-600 uppercase">{eyebrow}</p>
        <h2 className="font-display text-3xl font-semibold text-balance sm:text-4xl">{title}</h2>
        {body && <p className="mt-1 text-muted">{body}</p>}
      </div>
      {href && (
        <Link href={href} className="inline-flex shrink-0 items-center gap-1 text-sm font-semibold text-brand hover:underline">
          {t("market.home.seeAll")}
          <ArrowRight className="size-4" />
        </Link>
      )}
    </div>
  );
}

function ClassRow({ eyebrow, title, classes }: { eyebrow: string; title: string; classes: MarketClass[] }) {
  if (classes.length === 0) return null;
  return (
    <Container className="flex flex-col gap-6 pt-16 sm:pt-24">
      <SectionHead eyebrow={eyebrow} title={title} href="/classes" />
      <Lane label={title}>
        {classes.slice(0, 8).map((c, i) => <MarketClassCard key={c.id} c={c} index={i} />)}
      </Lane>
    </Container>
  );
}

/** The hero: the promise, search and popular subjects on the left; on the right a collage of real students with
 * neutral product cards (what a month includes, a live lesson). No teacher or class is promoted here. Below, the
 * platform's real totals. */
function Hero({ data }: { data: MarketHome | null }) {
  const subjects = (data?.subjects ?? []).filter((s) => s.class_count > 0).slice(0, 4);
  const subjectCount = (data?.subjects ?? []).filter((s) => s.class_count > 0).length;
  return (
    <section className="ez-grain relative isolate overflow-hidden bg-brand-950 text-on-brand">
      {/* Light: a warm glow behind the photos, a faint dot grid fading out, a cooler wash at the left. */}
      <div aria-hidden className="absolute -top-32 right-[-10%] -z-10 size-[720px] rounded-full bg-[radial-gradient(closest-side,rgb(212_160_63/0.28),transparent)]" />
      <div aria-hidden className="absolute -bottom-48 -left-40 -z-10 size-[560px] rounded-full bg-[radial-gradient(closest-side,rgb(35_128_90/0.35),transparent)]" />
      <div aria-hidden className="absolute inset-0 -z-10 bg-[radial-gradient(rgb(255_255_255/0.07)_1px,transparent_1px)] [mask-image:radial-gradient(ellipse_at_70%_40%,black,transparent_70%)] bg-[size:22px_22px]" />

      <Container className="grid items-center gap-14 pt-10 pb-14 sm:pt-14 lg:grid-cols-[1fr_1fr] lg:gap-12 lg:pt-14 lg:pb-14 [&>*]:min-w-0">
        <div className="flex flex-col items-start gap-6">
          <Link href="/courses"
                className="ez-rise group inline-flex items-center gap-2 rounded-full border border-white/12 bg-white/[0.06] py-1 pr-3 pl-1 text-xs font-semibold text-brand-100 backdrop-blur-sm transition hover:border-gold/50">
            <span className="rounded-full bg-gold px-2 py-0.5 text-[0.7rem] font-bold text-brand-950 uppercase">{t("home.hero.new")}</span>
            {t("home.hero.newText")}
            <ArrowRight className="size-3.5 transition group-hover:translate-x-0.5" />
          </Link>

          <h1 className="ez-rise font-display text-[2.7rem] leading-[1] font-semibold tracking-[-0.02em] text-balance sm:text-[3.5rem] lg:text-[4rem]"
              style={{ "--i": 1 } as React.CSSProperties}>
            {t("market.home.title")}{" "}
            <span className="relative inline-block text-gold-300 italic">
              {t("market.home.titleMark")}
              <svg aria-hidden viewBox="0 0 300 14" preserveAspectRatio="none" className="absolute -bottom-2 left-0 h-3 w-full text-gold/70">
                <path d="M2 9 C 70 2, 150 2, 298 7" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
              </svg>
            </span>
          </h1>

          <p className="ez-rise max-w-[34rem] text-lg leading-relaxed text-brand-100/80" style={{ "--i": 2 } as React.CSSProperties}>
            {t("market.home.body")}
          </p>

          <div className="ez-rise flex w-full max-w-[36rem] flex-col gap-3" style={{ "--i": 3 } as React.CSSProperties}>
            <form action="/classes" role="search"
                  className="flex w-full items-center gap-2 rounded-2xl bg-surface p-2 shadow-[0_24px_60px_-20px_rgb(0_0_0/0.6)] ring-1 ring-white/10 focus-within:ring-4 focus-within:ring-gold/40">
              <label className="flex min-w-0 flex-1 items-center gap-3 pl-3 text-foreground">
                <Search className="size-5 shrink-0 text-subtle" />
                <span className="sr-only">{t("market.search.label")}</span>
                <input name="q" placeholder={t("market.search.placeholder")}
                       className="min-h-12 w-full bg-transparent text-base outline-none placeholder:text-subtle" />
              </label>
              <button className={buttonStyles("primary", "lg", "rounded-xl px-6")}>{t("market.search.go")}</button>
            </form>
            {subjects.length > 0 && (
              <p className="flex flex-wrap items-center gap-x-1 gap-y-2 text-sm text-brand-100/70">
                <span className="mr-1">{t("home.hero.popular")}</span>
                {subjects.map((s) => (
                  <Link key={s.slug} href={`/${s.slug}`}
                        className="rounded-full border border-white/12 px-3 py-1 font-medium text-brand-100 transition hover:border-gold/60 hover:bg-white/[0.06] hover:text-on-brand">
                    {s.name}
                  </Link>
                ))}
              </p>
            )}
          </div>

          <ul className="ez-rise flex flex-wrap gap-x-6 gap-y-2 text-sm text-brand-100/85" style={{ "--i": 4 } as React.CSSProperties}>
            {[
              [<CalendarCheck key="a" />, t("home.trust.monthly")],
              [<MonitorPlay key="b" />, t("home.trust.live")],
              [<ShieldCheck key="c" />, t("home.trust.secure")],
            ].map(([icon, text], i) => (
              <li key={i} className="inline-flex items-center gap-2 [&>svg]:size-4 [&>svg]:text-gold">{icon}{text}</li>
            ))}
          </ul>
        </div>

        {/* The collage: three real moments of learning, and two neutral cards about the product. */}
        <div aria-hidden className="relative mx-auto w-full max-w-[560px]">
          <div className="grid grid-cols-[1.15fr_1fr] grid-rows-[repeat(6,minmax(0,1fr))] gap-3 sm:gap-4 aspect-[100/92]">
            <div className="ez-rise row-span-6 overflow-hidden rounded-[1.75rem] shadow-[0_40px_80px_-30px_rgb(0_0_0/0.8)] ring-1 ring-white/10" style={{ "--i": 2 } as React.CSSProperties}>
              <Photo photo={PHOTOS.hero} ratio={1.5} priority sizes="(min-width: 1024px) 330px, 52vw" className="h-full object-[55%_center]" />
            </div>
            <div className="ez-rise row-span-3 overflow-hidden rounded-[1.75rem] shadow-[0_30px_60px_-30px_rgb(0_0_0/0.8)] ring-1 ring-white/10" style={{ "--i": 3 } as React.CSSProperties}>
              <Photo photo={PHOTOS.online} ratio={0.85} priority sizes="(min-width: 1024px) 290px, 44vw" className="h-full" />
            </div>
            <div className="ez-rise row-span-3 overflow-hidden rounded-[1.75rem] shadow-[0_30px_60px_-30px_rgb(0_0_0/0.8)] ring-1 ring-white/10" style={{ "--i": 4 } as React.CSSProperties}>
              <Photo photo={PHOTOS.classroom} ratio={0.85} sizes="(min-width: 1024px) 290px, 44vw" className="h-full" />
            </div>
          </div>

          {/* A live lesson: across the gap between the two right-hand photos. */}
          <div className="ez-rise ez-float absolute top-[calc(50%-2rem)] -right-2 hidden items-center gap-3 rounded-2xl bg-surface/95 py-2.5 pr-4 pl-2.5 text-foreground shadow-[0_20px_40px_-16px_rgb(0_0_0/0.55)] ring-1 ring-black/5 backdrop-blur sm:flex lg:-right-6"
               style={{ "--i": 6 } as React.CSSProperties}>
            <span className="relative grid size-10 place-items-center rounded-xl bg-danger-bg text-danger">
              <Radio className="size-5" />
              <span className="absolute -top-0.5 -right-0.5 size-2.5 animate-ping rounded-full bg-danger" />
              <span className="absolute -top-0.5 -right-0.5 size-2.5 rounded-full bg-danger" />
            </span>
            <span className="flex flex-col leading-tight">
              <span className="text-sm font-semibold">{t("home.hero.liveTitle")}</span>
              <span className="text-xs text-muted">{t("home.hero.liveBody")}</span>
            </span>
          </div>

          {/* What a paid month includes: across the tall photo's lower edge. */}
          <div className="ez-rise ez-float-slow absolute -bottom-5 -left-3 hidden w-[min(17rem,62%)] sm:block rounded-2xl bg-surface p-4 text-foreground shadow-[0_24px_50px_-18px_rgb(0_0_0/0.6)] ring-1 ring-black/5 sm:-left-6 lg:-left-10"
               style={{ "--i": 7 } as React.CSSProperties}>
            <p className="text-[0.7rem] font-bold tracking-[0.12em] text-brand-600 uppercase">{t("home.hero.monthTitle")}</p>
            <ul className="mt-2.5 flex flex-col gap-2 text-sm">
              {[
                [<Radio key="a" />, t("home.hero.monthLive")],
                [<PlayCircle key="b" />, t("home.hero.monthRecordings")],
                [<FileText key="c" />, t("home.hero.monthTutes")],
              ].map(([icon, text], i) => (
                <li key={i} className="flex items-center gap-2.5">
                  <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand [&>svg]:size-4">{icon}</span>
                  <span className="min-w-0 flex-1 font-medium">{text}</span>
                  <Check className="size-4 shrink-0 text-success" />
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Container>

      {/* The platform in numbers (live totals from the marketplace), once they are worth showing. */}
      {data && showStats(data) && (
        <div className="border-t border-white/10 bg-black/15">
          <Container>
            <dl className="grid grid-cols-2 divide-white/10 py-6 sm:grid-cols-4 sm:divide-x">
              {[
                [data.classes, t("home.hero.statClasses")],
                [data.teachers, t("home.hero.statTeachers")],
                [subjectCount, t("home.hero.statSubjects")],
                [3, t("home.hero.statExams")],
              ].map(([n, label], i) => (
                <div key={i} className="flex flex-col gap-0.5 px-1 py-2 sm:px-6 sm:first:pl-0">
                  <dt className="order-2 text-sm text-brand-100/70">{label}</dt>
                  <dd className="order-1 font-display text-3xl font-semibold text-on-brand tabular-nums">{n}</dd>
                </div>
              ))}
            </dl>
          </Container>
        </div>
      )}
    </section>
  );
}

/** Three steps, each with a photo of that moment. */
function HowItWorks() {
  const steps = [
    { key: "find", photo: PHOTOS.classroom, icon: <Search /> },
    { key: "pay", photo: PHOTOS.phone, icon: <CreditCard /> },
    { key: "learn", photo: PHOTOS.online, icon: <MonitorPlay /> },
  ] as const;
  return (
    <Container className="flex flex-col gap-8 pt-16 sm:pt-24">
      <SectionHead eyebrow={t("home.how.eyebrow")} title={t("home.how.title")} />
      <ol className="grid gap-5 md:grid-cols-3">
        {steps.map((s, i) => (
          <li key={s.key} className="ez-rise group flex flex-col overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-sm"
              style={{ "--i": i } as React.CSSProperties}>
            <div className="relative overflow-hidden">
              <Photo photo={s.photo} ratio={0.62} sizes="(min-width: 768px) 33vw, 92vw"
                     className="aspect-[100/62] transition duration-700 ease-ez group-hover:scale-[1.04]" />
              <span className="absolute top-3 left-3 grid size-9 place-items-center rounded-full bg-surface font-display text-lg font-semibold text-brand shadow-ez">
                {i + 1}
              </span>
            </div>
            <div className="flex flex-1 flex-col gap-2 p-5">
              <p className="flex items-center gap-2 font-display text-xl font-semibold">
                <span className="text-brand-600 [&>svg]:size-5">{s.icon}</span>
                {t(`home.how.${s.key}.title`)}
              </p>
              <p className="text-[0.9375rem] leading-relaxed text-muted">{t(`home.how.${s.key}.body`)}</p>
            </div>
          </li>
        ))}
      </ol>
    </Container>
  );
}

/** Exam years: a photo of results day beside what EduZone gives across the year, with the live counts. */
function Results({ data }: { data: MarketHome }) {
  const subjects = data.subjects.filter((s) => s.class_count > 0).length;
  const points = [
    { icon: <CalendarCheck />, key: "monthly" },
    { icon: <Radio />, key: "recordings" },
    { icon: <Sparkles />, key: "catchup" },
  ] as const;
  return (
    <section className="mt-20 bg-sunken/60 py-16 sm:mt-28 sm:py-24">
      <Container className="grid items-center gap-10 lg:grid-cols-2 lg:gap-16 [&>*]:min-w-0">
        <div className="relative">
          <div className="overflow-hidden rounded-[2rem] shadow-ez-lg">
            <Photo photo={PHOTOS.graduate} ratio={0.8} sizes="(min-width: 1024px) 560px, 92vw" className="aspect-[100/80] object-[50%_30%]" />
          </div>
          {showStats(data) && <div className="absolute -bottom-6 left-4 right-4 grid grid-cols-3 gap-px overflow-hidden rounded-ez-lg border border-border bg-border shadow-ez-lg sm:left-8 sm:right-8">
            {[[data.classes, t("home.results.classes")], [data.teachers, t("home.results.teachers")], [subjects, t("home.results.subjects")]].map(([n, label]) => (
              <div key={String(label)} className="bg-surface px-3 py-3 text-center">
                <p className="font-display text-2xl font-semibold text-brand tabular-nums sm:text-3xl">{n}</p>
                <p className="text-xs text-muted">{label}</p>
              </div>
            ))}
          </div>}
        </div>
        <div className="flex flex-col gap-5 pt-8 lg:pt-0">
          <p className="text-xs font-bold tracking-[0.14em] text-brand-600 uppercase">{t("home.results.eyebrow")}</p>
          <h2 className="font-display text-3xl font-semibold text-balance sm:text-[2.6rem] sm:leading-[1.1]">{t("home.results.title")}</h2>
          <p className="text-lg leading-relaxed text-muted">{t("home.results.body")}</p>
          <ul className="flex flex-col gap-3">
            {points.map((p) => (
              <li key={p.key} className="flex gap-3">
                <span className="grid size-10 shrink-0 place-items-center rounded-ez bg-brand-50 text-brand [&>svg]:size-5">{p.icon}</span>
                <div>
                  <p className="font-semibold">{t(`home.results.${p.key}.title`)}</p>
                  <p className="text-sm text-muted">{t(`home.results.${p.key}.body`)}</p>
                </div>
              </li>
            ))}
          </ul>
          <Link href="/classes" className={buttonStyles("primary", "lg", "self-start")}>
            {t("home.results.cta")}<ArrowRight className="size-4.5" />
          </Link>
        </div>
      </Container>
    </section>
  );
}

/** For teachers: a teacher at the board, and why EduZone. */
function TeachBand() {
  return (
    <Container className="pt-16 sm:pt-24">
      <div className="ez-grain relative grid overflow-hidden rounded-[2rem] bg-brand-900 text-on-brand lg:grid-cols-[1.1fr_1fr]">
        <div className="flex flex-col items-start gap-5 p-8 sm:p-12 lg:p-14">
          <p className="text-xs font-bold tracking-[0.14em] text-gold uppercase">{t("market.home.teachEyebrow")}</p>
          <h2 className="font-display text-3xl font-semibold text-balance sm:text-[2.6rem] sm:leading-[1.1]">{t("market.home.teachTitle")}</h2>
          <p className="max-w-lg text-lg text-brand-100/85">{t("market.home.teachBody")}</p>
          <ul className="grid gap-2 text-brand-100/90 sm:grid-cols-2">
            {(["page", "fees", "video", "money"] as const).map((k) => (
              <li key={k} className="flex items-center gap-2 text-sm"><span className="size-1.5 rounded-full bg-gold" />{t(`home.teach.${k}`)}</li>
            ))}
          </ul>
          <Link href="/teach/apply" className={buttonStyles("gold", "lg")}>
            <GraduationCap className="size-5" />
            {t("market.home.teachCta")}
          </Link>
        </div>
        <div className="relative min-h-64 lg:min-h-full">
          <Photo photo={PHOTOS.teacherBoard} ratio={0.75} sizes="(min-width: 1024px) 560px, 100vw" className="absolute inset-0 h-full" />
          <div aria-hidden className="absolute inset-0 bg-gradient-to-r from-brand-900 via-brand-900/20 to-transparent max-lg:bg-gradient-to-b" />
        </div>
      </div>
    </Container>
  );
}

/** What students and parents ask before paying. */
function Faq() {
  return (
    <Container className="grid gap-8 py-16 sm:py-24 lg:grid-cols-[1fr_1.4fr] lg:gap-16 [&>*]:min-w-0">
      <div className="flex flex-col gap-3">
        <p className="text-xs font-bold tracking-[0.14em] text-brand-600 uppercase">{t("home.faq.eyebrow")}</p>
        <h2 className="font-display text-3xl font-semibold text-balance sm:text-4xl">{t("home.faq.title")}</h2>
        <p className="text-muted">{t("home.faq.body")}</p>
        <Link href="/contact" className="inline-flex items-center gap-1 self-start text-sm font-semibold text-brand hover:underline">
          {t("home.faq.contact")}<ArrowRight className="size-4" />
        </Link>
      </div>
      <div className="divide-y divide-border overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-sm">
        {FAQ.map((k, i) => (
          <details key={k} className="group" open={i === 0}>
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 font-semibold hover:bg-sunken/50 [&::-webkit-details-marker]:hidden">
              {t(`home.faq.${k}.q`)}
              <ChevronDown className="size-5 shrink-0 text-muted transition group-open:rotate-180" aria-hidden />
            </summary>
            <p className="px-5 pb-5 text-[0.9375rem] leading-relaxed text-muted">{t(`home.faq.${k}.a`)}</p>
          </details>
        ))}
      </div>
    </Container>
  );
}
