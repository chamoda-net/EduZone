import {
  ArrowDown, ArrowRight, BadgeCheck, ChevronRight, BookOpenCheck, Building2, CalendarCheck, Check, CreditCard, Fingerprint, GraduationCap, HeartHandshake,
  Landmark, Mail, MapPin, Quote, Radio, ReceiptText, Scale, ShieldCheck, Smartphone, Sparkles, Undo2, Users, X,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";

import type { Schema } from "@eduzone/api-client";
import { Photo } from "@/components/photo";
import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { PHOTOS, type Photo as PhotoT } from "@/lib/photos";
import { t, type MessageKey } from "@eduzone/lib/i18n";
import type { MarketHome } from "@eduzone/lib/types";
import { Container, buttonStyles, cx } from "@eduzone/ui";

export const metadata: Metadata = {
  title: `${t("about.eyebrow")} | EduZone`,
  description: t("about.meta"),
  alternates: { canonical: "/about" },
};

const rise = (i: number) => ({ "--i": i }) as CSSProperties;

/** About EduZone: the promise, the platform's live numbers, why it exists, what it believes, who it serves, how it
 * keeps payments and content safe, where it is going and the company behind it. Platform-level only: no teacher,
 * class or face is promoted here. */
export default async function AboutPage() {
  const [home, courses] = await Promise.all([
    api<MarketHome>("/market/home", { token: null }),
    api<Schema<"CoursesHome">>("/market/courses/home", { token: null }),
  ]);
  const data = home.ok ? home.data : null;
  const stats: Array<[number, MessageKey]> = data ? [
    [data.classes, "about.stat.classes"],
    [data.teachers, "about.stat.teachers"],
    [data.subjects.filter((s) => s.class_count > 0).length, "about.stat.subjects"],
    [courses.ok ? courses.data.total : 0, "about.stat.courses"],
  ] : [];

  return (
    <SiteShell bare>
      <Hero />
      {stats.length > 0 && <Stats stats={stats} />}
      <Story />
      <Values />
      <Audiences />
      <Trust />
      <Journey />
      <Company />
      <FinalCta />
    </SiteShell>
  );
}

function Eyebrow({ children, light = false }: { children: ReactNode; light?: boolean }) {
  return (
    <p className={cx("text-xs font-bold tracking-[0.14em] uppercase", light ? "text-gold" : "text-brand-600")}>{children}</p>
  );
}

/** A page header, deliberately quieter than the marketplace hero (which stays the site's biggest moment): breadcrumb,
 * a centred statement one size down from the home headline, then a low film strip of learning moments and product
 * facts that drifts sideways, then the mission as one sentence with photos set into the words. */
function Hero() {
  return (
    <section className="relative isolate overflow-hidden">
      {/* Ruled-paper lines fading out under the headline, and a warm glow. */}
      <div aria-hidden className="absolute inset-x-0 top-0 -z-10 h-[420px] bg-[linear-gradient(to_bottom,transparent_31px,rgb(26_67_49/0.06)_31px,rgb(26_67_49/0.06)_32px)] bg-[size:100%_32px] [mask-image:linear-gradient(to_bottom,black,transparent)]" />
      <div aria-hidden className="absolute -top-64 left-1/2 -z-10 size-[720px] -translate-x-1/2 rounded-full bg-[radial-gradient(closest-side,rgb(212_160_63/0.16),transparent)]" />

      <Container className="flex flex-col items-center pt-10 text-center sm:pt-14 lg:pt-16">
        <nav aria-label={t("about.breadcrumb")} className="ez-rise">
          <ol className="flex items-center gap-2 text-sm text-muted">
            <li><Link href="/" className="hover:text-foreground hover:underline">{t("about.home")}</Link></li>
            <li aria-hidden><ChevronRight className="size-3.5" /></li>
            <li aria-current="page" className="font-semibold text-brand">{t("about.eyebrow")}</li>
          </ol>
        </nav>
        <h1 className="ez-rise mt-5 max-w-3xl font-display text-[2.2rem] leading-[1.06] font-semibold tracking-[-0.02em] text-balance sm:text-[2.9rem] lg:text-[3.5rem]"
            style={rise(1)}>
          {t("about.titleStart")}{" "}
          <span className="relative mr-[0.12em] inline-block text-brand italic">
            {t("about.titleMark")}
            <svg aria-hidden viewBox="0 0 300 14" preserveAspectRatio="none" className="absolute -bottom-1 left-0 h-2.5 w-full text-gold">
              <path d="M2 9 C 70 2, 150 2, 298 7" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
            </svg>
          </span>{" "}
          {t("about.titleEnd")}
        </h1>
        <p className="ez-rise mt-5 max-w-xl text-base leading-relaxed text-muted sm:text-lg" style={rise(2)}>{t("about.body")}</p>
        <a href="#mission" className="ez-rise group mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-brand hover:underline" style={rise(3)}>
          {t("about.scroll")}
          <ArrowDown className="size-4 transition group-hover:translate-y-0.5" />
        </a>
      </Container>

      <FilmStrip />
      <Manifesto />
    </section>
  );
}

type Tile =
  | { kind: "photo"; photo: PhotoT; w: string; pos?: string }
  | { kind: "fact"; tone: "brand" | "gold"; icon: ReactNode; title: MessageKey; body: MessageKey };

/** Photos and three facts, alternately raised and lowered, sliding slowly to the left (paused on hover, still with
 * reduced motion). The list is rendered twice so the loop is seamless; the copy is hidden from screen readers. */
function FilmStrip() {
  const tiles: Tile[] = [
    { kind: "photo", photo: PHOTOS.reading, w: "w-[150px] sm:w-[190px]" },
    { kind: "fact", tone: "brand", icon: <Radio />, title: "about.tile.live", body: "about.tile.liveBody" },
    { kind: "photo", photo: PHOTOS.classroom, w: "w-[220px] sm:w-[290px]" },
    { kind: "photo", photo: PHOTOS.thinking, w: "w-[160px] sm:w-[205px]" },
    { kind: "fact", tone: "gold", icon: <GraduationCap />, title: "about.tile.exams", body: "about.tile.examsBody" },
    { kind: "photo", photo: PHOTOS.science, w: "w-[190px] sm:w-[250px]" },
    { kind: "photo", photo: PHOTOS.graduate, w: "w-[150px] sm:w-[190px]", pos: "object-[50%_30%]" },
    { kind: "fact", tone: "brand", icon: <CalendarCheck />, title: "about.tile.monthly", body: "about.tile.monthlyBody" },
    { kind: "photo", photo: PHOTOS.phone, w: "w-[205px] sm:w-[265px]" },
    { kind: "photo", photo: PHOTOS.chemistry, w: "w-[160px] sm:w-[205px]" },
  ];
  const render = (copy: number) => tiles.map((tile, i) => {
    const offset = i % 2 === 0 ? "mt-0" : "mt-6 sm:mt-9";
    if (tile.kind === "photo") {
      return (
        <li key={`${copy}-${i}`} aria-hidden={copy === 1 || undefined} className={cx("shrink-0 overflow-hidden rounded-[1.25rem] shadow-ez", tile.w, offset)}>
          <Photo photo={tile.photo} ratio={1} sizes="400px" priority={copy === 0 && i < 4}
                 className={cx("h-[170px] sm:h-[220px]", tile.pos)} />
        </li>
      );
    }
    return (
      <li key={`${copy}-${i}`} aria-hidden={copy === 1 || undefined}
          className={cx(
            "ez-grain relative flex h-[170px] w-[160px] shrink-0 flex-col justify-between overflow-hidden rounded-[1.25rem] p-4 shadow-ez sm:h-[220px] sm:w-[195px] sm:p-5",
            tile.tone === "brand" ? "bg-brand-900 text-on-brand" : "bg-gold text-brand-950", offset,
          )}>
        <span className={cx("grid size-10 place-items-center rounded-xl [&>svg]:size-5",
                            tile.tone === "brand" ? "bg-white/10 text-gold" : "bg-brand-950/10 text-brand-950")}>
          {tile.icon}
        </span>
        <span className="flex flex-col gap-1.5">
          <span className="font-display text-lg leading-tight font-semibold sm:text-xl">{t(tile.title)}</span>
          <span className={cx("text-xs sm:text-sm", tile.tone === "brand" ? "text-brand-100/75" : "text-brand-950/70")}>{t(tile.body)}</span>
        </span>
      </li>
    );
  });
  return (
    <div className="ez-rise relative mt-10 sm:mt-12" style={rise(4)}>
      <div className="overflow-hidden pb-4 [mask-image:linear-gradient(to_right,transparent,black_8%,black_92%,transparent)]">
        <ul className="ez-marquee flex w-max items-start gap-3 sm:gap-4" style={{ "--ez-marquee-time": "70s" } as CSSProperties}>
          {render(0)}
          {render(1)}
        </ul>
      </div>
    </div>
  );
}

/** The mission as one sentence: the key phrases in ink, the joins muted, small photos set into the line. */
function Manifesto() {
  const chip = (photo: PhotoT) => (
    <span aria-hidden className="mx-1 inline-block h-[0.78em] w-[1.6em] translate-y-[0.06em] overflow-hidden rounded-full align-baseline ring-2 ring-surface shadow-ez">
      <Photo photo={photo} ratio={0.5} sizes="120px" className="h-full" />
    </span>
  );
  return (
    <Container id="mission" className="grid scroll-mt-24 gap-6 pt-14 pb-16 sm:pt-20 sm:pb-20 lg:grid-cols-[12rem_1fr] lg:gap-12">
      <div className="lg:pt-3">
        <Eyebrow>{t("about.manifesto.label")}</Eyebrow>
        <span aria-hidden className="mt-3 block h-px w-16 bg-gold" />
      </div>
      <p className="font-display text-[1.5rem] leading-[1.3] font-medium tracking-[-0.01em] text-balance sm:text-[2rem] lg:text-[2.4rem]">
        <span className="text-subtle">{t("about.manifesto.a")}</span>
        {chip(PHOTOS.reading)}
        <span className="text-foreground">{t("about.manifesto.b")}</span>{" "}
        <span className="text-subtle">{t("about.manifesto.c")}</span>
        {chip(PHOTOS.teacherBoard)}
        <span className="text-foreground">{t("about.manifesto.d")}</span>{" "}
        <span className="text-subtle">{t("about.manifesto.e")}</span>
        <span aria-hidden className="mx-1 inline-grid size-[0.95em] translate-y-[0.12em] place-items-center rounded-full bg-gold text-brand-950 align-baseline">
          <Smartphone className="size-[0.55em]" />
        </span>
        <span className="text-brand italic">{t("about.manifesto.f")}</span>
      </p>
    </Container>
  );
}

/** Live totals from the marketplace. */
function Stats({ stats }: { stats: Array<[number, MessageKey]> }) {
  return (
    <section className="ez-grain relative bg-brand-950 text-on-brand">
      <Container>
        <dl className="grid grid-cols-2 gap-y-2 py-8 sm:py-10 lg:grid-cols-4 lg:divide-x lg:divide-white/10">
          {stats.map(([n, label]) => (
            <div key={label} className="flex flex-col gap-1 px-1 py-3 lg:px-8 lg:first:pl-0">
              <dt className="order-2 text-sm text-brand-100/70">{t(label)}</dt>
              <dd className="order-1 font-display text-4xl font-semibold text-gold-300 tabular-nums sm:text-5xl">{n}</dd>
            </div>
          ))}
        </dl>
      </Container>
    </section>
  );
}

/** Why EduZone exists, with a before/after of a tuition class's tools. */
function Story() {
  const rows = [1, 2, 3, 4] as const;
  return (
    <Container className="grid gap-12 pt-20 sm:pt-28 lg:grid-cols-[1fr_1fr] lg:gap-20 [&>*]:min-w-0">
      <div className="flex flex-col gap-5">
        <Eyebrow>{t("about.story.eyebrow")}</Eyebrow>
        <h2 className="font-display text-3xl font-semibold text-balance sm:text-[2.75rem] sm:leading-[1.08]">{t("about.story.title")}</h2>
        <div className="flex flex-col gap-4 text-[1.0625rem] leading-relaxed text-foreground/80">
          <p>{t("about.story.p1")}</p>
          <p>{t("about.story.p2")}</p>
          <p>{t("about.story.p3")}</p>
        </div>
        <figure className="mt-3 rounded-ez-lg border-l-4 border-gold bg-gold/[0.07] py-5 pr-6 pl-6">
          <Quote aria-hidden className="size-6 text-gold" />
          <blockquote className="mt-2 font-display text-xl leading-snug font-medium text-balance text-foreground">
            {t("about.story.quote")}
          </blockquote>
          <figcaption className="mt-3 text-sm font-semibold text-muted">{t("about.story.quoteBy")}</figcaption>
        </figure>
      </div>

      <div className="flex flex-col justify-center lg:sticky lg:top-28 lg:self-start">
        <div className="overflow-hidden rounded-[1.75rem] border border-border bg-surface shadow-ez-lg">
          <div className="grid grid-cols-2 border-b border-border text-sm font-bold">
            <p className="flex items-center gap-2 bg-sunken/70 px-5 py-4 text-muted">
              <span className="size-2 rounded-full bg-danger" />{t("about.problem.before")}
            </p>
            <p className="flex items-center gap-2 bg-brand-50 px-5 py-4 text-brand">
              <span className="size-2 rounded-full bg-success" />{t("about.problem.after")}
            </p>
          </div>
          <ul className="divide-y divide-border">
            {rows.map((n) => (
              <li key={n} className="grid grid-cols-2">
                <p className="flex gap-2.5 px-5 py-4 text-sm text-muted">
                  <X className="mt-0.5 size-4 shrink-0 text-danger" />
                  <span className="line-through decoration-danger/30">{t(`about.problem.b${n}`)}</span>
                </p>
                <p className="flex gap-2.5 border-l border-border bg-brand-50/40 px-5 py-4 text-sm font-medium">
                  <Check className="mt-0.5 size-4 shrink-0 text-success" />{t(`about.problem.a${n}`)}
                </p>
              </li>
            ))}
          </ul>
        </div>
        <div className="mt-5 overflow-hidden rounded-[1.75rem] shadow-ez-lg">
          <Photo photo={PHOTOS.online} ratio={0.5} sizes="(min-width: 1024px) 540px, 92vw" className="aspect-[2/1]" />
        </div>
      </div>
    </Container>
  );
}

/** Four promises, numbered like chapters. */
function Values() {
  const values = [
    { key: "students", icon: <HeartHandshake /> },
    { key: "teachers", icon: <BookOpenCheck /> },
    { key: "money", icon: <Scale /> },
    { key: "local", icon: <Smartphone /> },
  ] as const;
  return (
    <section className="mt-20 bg-sunken/60 py-20 sm:mt-28 sm:py-28">
      <Container className="flex flex-col gap-10">
        <div className="flex max-w-2xl flex-col gap-2">
          <Eyebrow>{t("about.values.eyebrow")}</Eyebrow>
          <h2 className="font-display text-3xl font-semibold text-balance sm:text-[2.75rem] sm:leading-[1.08]">{t("about.values.title")}</h2>
        </div>
        <ol className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {values.map((v, i) => (
            <li key={v.key}
                className="group relative flex flex-col gap-4 overflow-hidden rounded-ez-lg border border-border bg-surface p-6 shadow-ez-sm transition duration-300 ease-ez hover:-translate-y-1 hover:shadow-ez-lg">
              <span aria-hidden className="absolute -top-4 -right-1 font-display text-[6.5rem] leading-none font-semibold text-brand/[0.06] transition group-hover:text-gold/20">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="grid size-12 place-items-center rounded-ez bg-brand text-on-brand shadow-ez [&>svg]:size-6">{v.icon}</span>
              <h3 className="font-display text-xl font-semibold">{t(`about.values.${v.key}.title`)}</h3>
              <p className="text-[0.9375rem] leading-relaxed text-muted">{t(`about.values.${v.key}.body`)}</p>
            </li>
          ))}
        </ol>
      </Container>
    </section>
  );
}

/** Students, teachers, institutes: what each gets, with a way in. */
function Audiences() {
  const groups: Array<{ key: "students" | "teachers" | "institutes"; photo: PhotoT; icon: ReactNode; href: string }> = [
    { key: "students", photo: PHOTOS.phone, icon: <GraduationCap />, href: "/classes" },
    { key: "teachers", photo: PHOTOS.teacherBoard, icon: <Users />, href: "/teach/apply" },
    { key: "institutes", photo: PHOTOS.classroom, icon: <Building2 />, href: "/institutes" },
  ];
  return (
    <Container className="flex flex-col gap-10 pt-20 sm:pt-28">
      <div className="flex max-w-2xl flex-col gap-2">
        <Eyebrow>{t("about.who.eyebrow")}</Eyebrow>
        <h2 className="font-display text-3xl font-semibold text-balance sm:text-[2.75rem] sm:leading-[1.08]">{t("about.who.title")}</h2>
      </div>
      <div className="grid gap-5 lg:grid-cols-3">
        {groups.map((g) => (
          <article key={g.key} className="group flex flex-col overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-sm">
            <div className="relative overflow-hidden">
              <Photo photo={g.photo} ratio={0.58} sizes="(min-width: 1024px) 33vw, 92vw"
                     className="aspect-[100/58] transition duration-700 ease-ez group-hover:scale-[1.04]" />
              <div aria-hidden className="absolute inset-0 bg-gradient-to-t from-brand-950/70 via-brand-950/10 to-transparent" />
              <h3 className="absolute bottom-4 left-5 flex items-center gap-2.5 font-display text-2xl font-semibold text-on-brand">
                <span className="grid size-9 place-items-center rounded-full bg-gold text-brand-950 [&>svg]:size-5">{g.icon}</span>
                {t(`about.who.${g.key}.title`)}
              </h3>
            </div>
            <div className="flex flex-1 flex-col gap-4 p-6">
              <p className="text-[0.9375rem] leading-relaxed text-muted">{t(`about.who.${g.key}.body`)}</p>
              <ul className="flex flex-col gap-2.5">
                {([1, 2, 3] as const).map((n) => (
                  <li key={n} className="flex items-start gap-2.5 text-sm font-medium">
                    <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-success-bg text-success"><Check className="size-3.5" /></span>
                    {t(`about.who.${g.key}.p${n}`)}
                  </li>
                ))}
              </ul>
              <Link href={g.href} className="mt-auto inline-flex items-center gap-1.5 self-start pt-2 text-sm font-semibold text-brand hover:underline">
                {t(`about.who.${g.key}.cta`)}<ArrowRight className="size-4 transition group-hover:translate-x-0.5" />
              </Link>
            </div>
          </article>
        ))}
      </div>
    </Container>
  );
}

/** What protects students and teachers, on the brand's dark green. */
function Trust() {
  const items = [
    { key: "review", icon: <BadgeCheck /> },
    { key: "cards", icon: <CreditCard /> },
    { key: "device", icon: <Fingerprint /> },
    { key: "watermark", icon: <ShieldCheck /> },
    { key: "refunds", icon: <Undo2 /> },
    { key: "ledger", icon: <ReceiptText /> },
  ] as const;
  return (
    <Container className="pt-20 sm:pt-28">
      <section className="ez-grain relative overflow-hidden rounded-[2rem] bg-brand-900 px-6 py-12 text-on-brand sm:px-12 sm:py-16 lg:px-16">
        <div aria-hidden className="absolute -top-32 -right-24 size-[420px] rounded-full bg-[radial-gradient(closest-side,rgb(212_160_63/0.22),transparent)]" />
        <div className="relative grid gap-10 lg:grid-cols-[0.9fr_1.6fr] lg:gap-16 [&>*]:min-w-0">
          <div className="flex flex-col gap-4">
            <Eyebrow light>{t("about.trust.eyebrow")}</Eyebrow>
            <h2 className="font-display text-3xl font-semibold text-balance sm:text-[2.6rem] sm:leading-[1.1]">{t("about.trust.title")}</h2>
            <p className="text-lg leading-relaxed text-brand-100/80">{t("about.trust.body")}</p>
            <Link href="/refund-policy" className="inline-flex items-center gap-1.5 self-start text-sm font-semibold text-gold-300 hover:underline">
              {t("static.refunds.title")}<ArrowRight className="size-4" />
            </Link>
          </div>
          <ul className="grid gap-px overflow-hidden rounded-ez-lg bg-white/10 sm:grid-cols-2">
            {items.map((it) => (
              <li key={it.key} className="flex gap-4 bg-brand-900 p-5 transition hover:bg-brand-800/80">
                <span className="grid size-11 shrink-0 place-items-center rounded-ez bg-white/[0.07] text-gold ring-1 ring-white/10 [&>svg]:size-5">{it.icon}</span>
                <div className="flex flex-col gap-1">
                  <p className="font-semibold">{t(`about.trust.${it.key}.title`)}</p>
                  <p className="text-sm leading-relaxed text-brand-100/70">{t(`about.trust.${it.key}.body`)}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </Container>
  );
}

/** Milestones: what is built, what is happening now, what comes later. */
function Journey() {
  const steps = [
    { key: "market", state: "done" },
    { key: "courses", state: "done" },
    { key: "pilot", state: "now" },
    { key: "languages", state: "later" },
    { key: "companies", state: "later" },
  ] as const;
  const pill = {
    done: "bg-success-bg text-success",
    now: "bg-gold text-brand-950",
    later: "bg-sunken text-muted",
  } as const;
  return (
    <Container className="flex flex-col gap-10 pt-20 sm:pt-28">
      <div className="flex max-w-2xl flex-col gap-2">
        <Eyebrow>{t("about.journey.eyebrow")}</Eyebrow>
        <h2 className="font-display text-3xl font-semibold text-balance sm:text-[2.75rem] sm:leading-[1.08]">{t("about.journey.title")}</h2>
      </div>
      <ol className="relative grid gap-6 lg:grid-cols-5 lg:gap-5">
        <span aria-hidden className="absolute top-5 bottom-5 left-5 w-px bg-border-strong lg:top-5 lg:right-5 lg:bottom-auto lg:left-5 lg:h-px lg:w-auto" />
        {steps.map((s) => (
          <li key={s.key} className="relative flex gap-4 lg:flex-col">
            <span className={cx(
              "relative z-10 grid size-10 shrink-0 place-items-center rounded-full border-4 border-background",
              s.state === "done" ? "bg-brand text-on-brand" : s.state === "now" ? "bg-gold text-brand-950" : "bg-surface text-muted ring-1 ring-border-strong",
            )}>
              {s.state === "done" ? <Check className="size-4.5" /> : s.state === "now" ? <Sparkles className="size-4.5" /> : <span className="size-2 rounded-full bg-border-strong" />}
              {s.state === "now" && <span aria-hidden className="absolute inset-0 animate-ping rounded-full bg-gold/40" />}
            </span>
            <div className="flex flex-col gap-1.5 pb-1">
              <span className={cx("self-start rounded-full px-2.5 py-0.5 text-[0.7rem] font-bold tracking-wide uppercase", pill[s.state])}>
                {t(`about.journey.${s.state}`)}
              </span>
              <h3 className="font-display text-lg font-semibold">{t(`about.journey.${s.key}.title`)}</h3>
              <p className="text-sm leading-relaxed text-muted">{t(`about.journey.${s.key}.body`)}</p>
            </div>
          </li>
        ))}
      </ol>
    </Container>
  );
}

/** The company behind EduZone. */
function Company() {
  const facts: Array<{ icon: ReactNode; label: MessageKey; value: ReactNode }> = [
    { icon: <Landmark />, label: "about.company.name", value: t("about.company.nameValue") },
    { icon: <MapPin />, label: "about.company.country", value: t("about.company.countryValue") },
    {
      icon: <Mail />, label: "about.company.email",
      value: <a href={`mailto:${t("about.company.emailValue")}`} className="break-all text-brand hover:underline">{t("about.company.emailValue")}</a>,
    },
  ];
  return (
    <Container className="pt-20 sm:pt-28">
      <div className="grid items-center gap-10 rounded-[2rem] border border-border bg-surface p-6 shadow-ez-sm sm:p-10 lg:grid-cols-[1.2fr_1fr] lg:gap-16 lg:p-14 [&>*]:min-w-0">
        <div className="flex flex-col gap-4">
          <Eyebrow>{t("about.company.eyebrow")}</Eyebrow>
          <h2 className="font-display text-3xl font-semibold text-balance sm:text-4xl">{t("about.company.title")}</h2>
          <p className="text-lg leading-relaxed text-muted">{t("about.company.body")}</p>
          <Link href="/contact" className={buttonStyles("secondary", "md", "self-start")}>
            <Mail className="size-4" />{t("about.company.contact")}
          </Link>
        </div>
        <dl className="flex flex-col divide-y divide-border rounded-ez-lg border border-border bg-sunken/40">
          {facts.map((f) => (
            <div key={f.label} className="flex items-center gap-4 px-5 py-4">
              <span className="grid size-10 shrink-0 place-items-center rounded-ez bg-brand-50 text-brand [&>svg]:size-5">{f.icon}</span>
              <div className="min-w-0">
                <dt className="text-xs font-semibold tracking-wide text-muted uppercase">{t(f.label)}</dt>
                <dd className="font-semibold">{f.value}</dd>
              </div>
            </div>
          ))}
        </dl>
      </div>
    </Container>
  );
}

/** The last word: two ways in. */
function FinalCta() {
  return (
    <Container className="py-20 sm:py-28">
      <div className="relative overflow-hidden rounded-[2rem] bg-brand-950 text-on-brand">
        <Photo photo={PHOTOS.hero} ratio={0.42} sizes="(min-width: 1280px) 1200px, 100vw" className="absolute inset-0 h-full opacity-35" />
        <div aria-hidden className="absolute inset-0 bg-gradient-to-r from-brand-950 via-brand-950/85 to-brand-950/40" />
        <div className="relative flex flex-col items-start gap-5 px-6 py-14 sm:px-12 sm:py-20 lg:px-16">
          <h2 className="max-w-xl font-display text-4xl font-semibold text-balance sm:text-5xl">{t("about.cta.title")}</h2>
          <p className="max-w-lg text-lg text-brand-100/85">{t("about.cta.body")}</p>
          <div className="flex flex-wrap gap-3 pt-2">
            <Link href="/classes" className={buttonStyles("gold", "lg")}>
              {t("about.ctaStudents")}<ArrowRight className="size-4.5" />
            </Link>
            <Link href="/teach/apply"
                  className="inline-flex min-h-12 items-center gap-2 rounded-ez border border-white/25 px-6 font-semibold text-on-brand transition hover:bg-white/10">
              <GraduationCap className="size-5" />{t("about.ctaTeachers")}
            </Link>
          </div>
        </div>
      </div>
    </Container>
  );
}
