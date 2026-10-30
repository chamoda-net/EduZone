import { ArrowRight, CalendarCheck, GraduationCap, MonitorPlay, Search, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { MarketClassCard } from "@/components/market-card";
import { SiteShell } from "@/components/shell";
import { SubjectTile } from "@/components/subject-tile";
import { api, userHost } from "@/lib/api";
import { isMainHost, mainOrigin } from "@/lib/site";
import { errorText, t } from "@eduzone/lib/i18n";
import type { MarketClass, MarketHome } from "@eduzone/lib/types";
import { ClassCover, Container, ErrorText, buttonStyles } from "@eduzone/ui";

const EXAMS = ["grade_5", "ol", "al"] as const;

/** The marketplace home. A tenant's old subdomain now points to its classes on the main site. */
export default async function Home() {
  if (!(await isMainHost())) {
    const slug = (await userHost()).split(".")[0];
    redirect(`${await mainOrigin()}/classes?org=${encodeURIComponent(slug)}`);
  }
  const res = await api<MarketHome>("/market/home", { token: null });

  return (
    <SiteShell bare>
      <Hero data={res.ok ? res.data : null} />

      <Container className="relative z-10 -mt-10 sm:-mt-12">
        <ul className="grid gap-px overflow-hidden rounded-ez-lg border border-border bg-border shadow-ez sm:grid-cols-3">
          {[
            { icon: <CalendarCheck />, title: t("home.trust.monthly"), body: t("home.trust.monthlyBody") },
            { icon: <MonitorPlay />, title: t("home.trust.live"), body: t("home.trust.liveBody") },
            { icon: <ShieldCheck />, title: t("home.trust.secure"), body: t("home.trust.secureBody") },
          ].map((item, i) => (
            <li key={i} className="ez-rise flex gap-4 bg-surface p-5" style={{ "--i": i + 2 } as React.CSSProperties}>
              <span className="grid size-10 shrink-0 place-items-center rounded-ez bg-brand-50 text-brand [&>svg]:size-5">{item.icon}</span>
              <div>
                <p className="font-semibold">{item.title}</p>
                <p className="text-sm text-muted">{item.body}</p>
              </div>
            </li>
          ))}
        </ul>
      </Container>

      {!res.ok && <Container className="py-10"><ErrorText>{errorText(t, res.error)}</ErrorText></Container>}
      {res.ok && (
        <>
          <Container className="flex flex-col gap-6 pt-16 sm:pt-20">
            <SectionHead eyebrow={t("market.home.subjectsEyebrow")} title={t("market.home.subjects")} href="/classes" />
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {res.data.subjects.filter((s) => s.class_count > 0).concat(res.data.subjects.filter((s) => s.class_count === 0))
                .slice(0, 8).map((s, i) => <SubjectTile key={s.slug} s={s} i={i} />)}
            </ul>
          </Container>

          {res.data.starting.length > 0 && (
            <ClassRow eyebrow={t("market.home.startingEyebrow")} title={t("market.home.starting")} classes={res.data.starting} />
          )}
          <ClassRow eyebrow={t("market.home.popularEyebrow")} title={t("market.home.popular")} classes={res.data.popular} />

          <Container className="py-16 sm:py-20">
            <div className="ez-grain relative flex flex-col items-start gap-5 overflow-hidden rounded-ez-lg bg-brand-900 p-8 text-on-brand sm:flex-row sm:items-center sm:justify-between sm:p-12">
              <div className="flex max-w-xl flex-col gap-3">
                <p className="text-xs font-bold tracking-[0.14em] text-gold uppercase">{t("market.home.teachEyebrow")}</p>
                <h2 className="font-display text-3xl font-semibold sm:text-4xl">{t("market.home.teachTitle")}</h2>
                <p className="text-brand-100/80">{t("market.home.teachBody")}</p>
              </div>
              <Link href="/register?next=/teach" className={buttonStyles("gold", "lg")}>
                <GraduationCap className="size-5" />
                {t("market.home.teachCta")}
              </Link>
            </div>
          </Container>
        </>
      )}
    </SiteShell>
  );
}

function SectionHead({ eyebrow, title, href }: { eyebrow: string; title: string; href?: string }) {
  return (
    <div className="flex items-end justify-between gap-4">
      <div>
        <p className="text-xs font-bold tracking-[0.14em] text-brand-600 uppercase">{eyebrow}</p>
        <h2 className="font-display text-3xl font-semibold sm:text-4xl">{title}</h2>
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
    <Container className="flex flex-col gap-6 pt-16 sm:pt-20">
      <SectionHead eyebrow={eyebrow} title={title} href="/classes" />
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {classes.slice(0, 8).map((c, i) => <MarketClassCard key={c.id} c={c} index={i} />)}
      </div>
    </Container>
  );
}

function Hero({ data }: { data: MarketHome | null }) {
  const covers = (data?.popular ?? []).slice(0, 3);
  const books = [0, 1, 2].map((i) => covers[i] ?? { title: ["Physics", "Combined Maths", "Biology"][i], subject_name: ["Physics", "Combined Maths", "Biology"][i], exam: null });
  return (
    <section className="ez-grain relative overflow-hidden bg-brand-900 text-on-brand">
      <svg aria-hidden viewBox="0 0 800 600" className="absolute -top-40 -right-40 w-[720px] opacity-50">
        {[120, 190, 260, 330].map((r) => (
          <circle key={r} cx="400" cy="300" r={r} fill="none" stroke="var(--ez-brand-600)" strokeWidth="1" />
        ))}
        <circle cx="400" cy="300" r="70" fill="var(--ez-gold-500)" opacity="0.18" />
      </svg>

      <Container className="relative grid items-center gap-12 pt-14 pb-24 sm:pt-20 sm:pb-28 lg:grid-cols-[1.15fr_1fr] lg:pt-24 lg:pb-32 [&>*]:min-w-0">
        <div className="flex flex-col items-start gap-6">
          <p className="ez-rise inline-flex items-center gap-2 rounded-full border border-brand-600/60 bg-brand-800/60 px-3 py-1 text-xs font-semibold tracking-wide text-brand-100">
            <span className="size-1.5 rounded-full bg-gold" />
            {data ? t("market.home.counts", { classes: data.classes, teachers: data.teachers }) : "EduZone"}
          </p>
          <h1 className="ez-rise font-display text-[2.6rem] leading-[1.02] font-semibold sm:text-6xl lg:text-[4.2rem]"
              style={{ "--i": 1 } as React.CSSProperties}>
            {t("market.home.title")} <span className="text-gold-300 italic">{t("market.home.titleMark")}</span>
          </h1>
          <p className="ez-rise max-w-xl text-lg leading-relaxed text-brand-100/85" style={{ "--i": 2 } as React.CSSProperties}>
            {t("market.home.body")}
          </p>
          <form action="/classes" className="ez-rise flex w-full max-w-xl gap-2 rounded-ez-lg bg-surface p-2 shadow-ez-lg"
                style={{ "--i": 3 } as React.CSSProperties} role="search">
            <label className="flex flex-1 items-center gap-2 px-2 text-foreground">
              <Search className="size-5 shrink-0 text-subtle" />
              <span className="sr-only">{t("market.search.label")}</span>
              <input name="q" placeholder={t("market.search.placeholder")}
                     className="min-h-11 w-full bg-transparent text-[0.9375rem] outline-none placeholder:text-subtle" />
            </label>
            <button className={buttonStyles("primary")}>{t("market.search.go")}</button>
          </form>
          <div className="ez-rise flex flex-wrap gap-2" style={{ "--i": 4 } as React.CSSProperties}>
            {EXAMS.map((e) => (
              <Link key={e} href={`/classes?exam=${e}`}
                    className="rounded-full border border-brand-600/60 px-4 py-1.5 text-sm font-semibold text-brand-100 transition hover:border-gold hover:text-on-brand">
                {t(`exam.${e}`)}
              </Link>
            ))}
          </div>
        </div>

        <div aria-hidden className="relative mx-auto hidden h-[360px] w-full max-w-[460px] sm:block">
          {books.map((b, i) => (
            <div
              key={i}
              className="ez-rise absolute w-[64%] overflow-hidden rounded-ez-lg border border-white/10 shadow-[0_30px_60px_-20px_rgb(0_0_0/0.6)]"
              style={{ "--i": 3 + i, left: `${[0, 18, 36][i]}%`, top: `${[18, 2, 30][i]}%`, rotate: `${[-8, 3, 10][i]}deg`,
                       zIndex: [1, 3, 2][i] } as React.CSSProperties}
            >
              <ClassCover title={b.title} subject={b.subject_name} label={b.exam ? t(`exam.${b.exam}`) : null} size="lg" />
            </div>
          ))}
        </div>
      </Container>
    </section>
  );
}
