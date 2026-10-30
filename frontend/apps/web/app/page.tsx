import { ArrowRight, CalendarCheck, LibraryBig, MonitorPlay, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { ClassCard } from "@/components/class-card";
import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { getBranding, getMe } from "@/lib/session";
import { isMainHost } from "@/lib/site";
import { errorText, t } from "@eduzone/lib/i18n";
import type { ClassItem, PublicClass, PublicClassPage } from "@eduzone/lib/types";
import { ClassCover, Container, EmptyState, ErrorText, FilterChips, buttonStyles } from "@eduzone/ui";

type Exam = NonNullable<ClassItem["exam"]>;
const EXAMS: Exam[] = ["al", "ol", "grade_5", "other"];

/** The tenant's public home: its published classes, open to anyone. */
export default async function Home({ searchParams }: PageProps<"/">) {
  // The main site has no catalogue until the marketplace (phase 4): the student area or sign-in.
  if (await isMainHost()) {
    if (await getMe()) redirect("/learn");
    return <MainWelcome />;
  }
  const sp = await searchParams;
  const exam = EXAMS.includes(sp.exam as Exam) ? (sp.exam as Exam) : null;
  const cursor = typeof sp.cursor === "string" ? sp.cursor : null;
  const q = new URLSearchParams({ limit: "24" });
  if (exam) q.set("exam", exam);
  if (cursor) q.set("cursor", cursor);
  const [branding, me, res] = await Promise.all([
    getBranding(),
    getMe(),
    api<PublicClassPage>(`/public/classes?${q}`, { token: null }),
  ]);
  const classes = res.ok ? res.data.items : [];

  return (
    <SiteShell bare>
      <Hero org={branding?.name ?? ""} signedIn={Boolean(me)} covers={classes.slice(0, 3)} />

      <Container className="relative z-10 -mt-10 sm:-mt-12">
        <ul className="grid gap-px overflow-hidden rounded-ez-lg border border-border bg-border shadow-ez sm:grid-cols-3">
          {[
            { icon: <CalendarCheck />, title: t("home.trust.monthly"), body: t("home.trust.monthlyBody") },
            { icon: <MonitorPlay />, title: t("home.trust.live"), body: t("home.trust.liveBody") },
            { icon: <ShieldCheck />, title: t("home.trust.secure"), body: t("home.trust.secureBody") },
          ].map((item, i) => (
            <li key={i} className="ez-rise flex gap-4 bg-surface p-5" style={{ "--i": i + 2 } as React.CSSProperties}>
              <span className="grid size-10 shrink-0 place-items-center rounded-ez bg-brand-50 text-brand [&>svg]:size-5">
                {item.icon}
              </span>
              <div>
                <p className="font-semibold">{item.title}</p>
                <p className="text-sm text-muted">{item.body}</p>
              </div>
            </li>
          ))}
        </ul>
      </Container>

      <Container id="classes" className="flex scroll-mt-20 flex-col gap-6 py-14 sm:py-20">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-bold tracking-[0.14em] text-brand-600 uppercase">{t("home.classes.eyebrow")}</p>
            <h2 className="font-display text-3xl font-semibold sm:text-4xl">{t("home.classes.title")}</h2>
          </div>
          <FilterChips
            label={t("home.classes.filter")}
            items={[null, ...EXAMS].map((e) => ({
              href: e ? `/?exam=${e}#classes` : "/#classes",
              label: e ? t(`exam.${e}`) : t("classes.filter.all"),
              active: e === exam,
            }))}
          />
        </div>

        {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
        {res.ok && classes.length === 0 && (
          <EmptyState icon={<LibraryBig />} title={t("catalog.emptyTitle")} body={t("catalog.empty")} />
        )}
        {classes.length > 0 && (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {classes.map((c, i) => (
              <ClassCard key={c.id} c={c} index={i} />
            ))}
          </div>
        )}
        {res.ok && res.data.next_cursor && (
          <Link
            href={`/?${new URLSearchParams({ ...(exam ? { exam } : {}), cursor: res.data.next_cursor })}#classes`}
            className={buttonStyles("secondary", "md", "self-center")}
          >
            {t("classes.loadMore")}
          </Link>
        )}
      </Container>
    </SiteShell>
  );
}

function Hero({ org, signedIn, covers }: { org: string; signedIn: boolean; covers: PublicClass[] }) {
  const books = [0, 1, 2].map((i) => covers[i] ?? { title: ["Physics", "Mathematics", "Biology"][i], subject: ["Physics", "Mathematics", "Biology"][i], exam: null });
  return (
    <section className="ez-grain relative overflow-hidden bg-brand-900 text-on-brand">
      <svg aria-hidden viewBox="0 0 800 600" className="absolute -top-40 -right-40 w-[720px] opacity-50">
        {[120, 190, 260, 330].map((r) => (
          <circle key={r} cx="400" cy="300" r={r} fill="none" stroke="var(--ez-brand-600)" strokeWidth="1" />
        ))}
        <circle cx="400" cy="300" r="70" fill="var(--ez-gold-500)" opacity="0.18" />
      </svg>

      <Container className="relative grid items-center gap-12 pt-14 pb-24 sm:pt-20 sm:pb-28 lg:grid-cols-[1.15fr_1fr] lg:pt-24 lg:pb-32">
        <div className="flex flex-col items-start gap-6">
          <p className="ez-rise inline-flex items-center gap-2 rounded-full border border-brand-600/60 bg-brand-800/60 px-3 py-1 text-xs font-semibold tracking-wide text-brand-100">
            <span className="size-1.5 rounded-full bg-gold" />
            {t("home.hero.eyebrow", { org })}
          </p>
          <h1
            className="ez-rise font-display text-[2.6rem] leading-[1.02] font-semibold sm:text-6xl lg:text-[4.2rem]"
            style={{ "--i": 1 } as React.CSSProperties}
          >
            {t("home.hero.title")}{" "}
            <em className="text-gold-300 not-italic">
              <span className="italic">{t("home.hero.titleMark")}</span>
            </em>
          </h1>
          <p className="ez-rise max-w-xl text-lg leading-relaxed text-brand-100/85" style={{ "--i": 2 } as React.CSSProperties}>
            {t("home.hero.body")}
          </p>
          <div className="ez-rise flex flex-wrap gap-3" style={{ "--i": 3 } as React.CSSProperties}>
            <Link href="#classes" className={buttonStyles("gold", "lg")}>
              {t("home.hero.cta")}
              <ArrowRight className="size-4.5 transition-transform group-hover/btn:translate-x-0.5" />
            </Link>
            {signedIn ? (
              <Link href="/my" className={buttonStyles("ghost", "lg", "text-on-brand hover:bg-brand-800")}>
                {t("home.hero.ctaMine")}
              </Link>
            ) : (
              <Link href="/login" className={buttonStyles("ghost", "lg", "text-on-brand hover:bg-brand-800")}>
                {t("home.signIn")}
              </Link>
            )}
          </div>
        </div>

        {/* A small fan of real class covers, like books on a desk. */}
        <div aria-hidden className="relative mx-auto hidden h-[360px] w-full max-w-[460px] sm:block">
          {books.map((b, i) => (
            <div
              key={i}
              className="ez-rise absolute w-[64%] overflow-hidden rounded-ez-lg border border-white/10 shadow-[0_30px_60px_-20px_rgb(0_0_0/0.6)]"
              style={
                {
                  "--i": 3 + i,
                  left: `${[0, 18, 36][i]}%`,
                  top: `${[18, 2, 30][i]}%`,
                  rotate: `${[-8, 3, 10][i]}deg`,
                  zIndex: [1, 3, 2][i],
                } as React.CSSProperties
              }
            >
              <ClassCover title={b.title} subject={b.subject} label={b.exam ? t(`exam.${b.exam}`) : null} size="lg" />
            </div>
          ))}
          <div className="absolute right-0 bottom-0 z-10 rounded-ez bg-surface px-4 py-3 text-foreground shadow-ez-lg">
            <p className="text-xs font-semibold text-muted">{t("home.hero.badgeLabel")}</p>
            <p className="font-display text-lg font-semibold text-brand">{t("home.hero.badge")}</p>
          </div>
        </div>
      </Container>
    </section>
  );
}

function MainWelcome() {
  return (
    <SiteShell bare>
      <section className="ez-grain relative flex flex-1 items-center overflow-hidden bg-brand-900 text-on-brand">
        <svg aria-hidden viewBox="0 0 800 600" className="absolute -top-40 -right-40 w-[720px] opacity-50">
          {[120, 190, 260, 330].map((r) => (
            <circle key={r} cx="400" cy="300" r={r} fill="none" stroke="var(--ez-brand-600)" strokeWidth="1" />
          ))}
          <circle cx="400" cy="300" r="70" fill="var(--ez-gold-500)" opacity="0.18" />
        </svg>
        <Container className="relative flex flex-col items-start gap-6 py-24 sm:py-32">
          <h1 className="ez-rise max-w-2xl font-display text-5xl leading-[1.02] font-semibold sm:text-6xl">
            {t("learn.mainHome.title")}
          </h1>
          <p className="ez-rise max-w-xl text-lg text-brand-100/85" style={{ "--i": 1 } as React.CSSProperties}>
            {t("learn.mainHome.body")}
          </p>
          <div className="ez-rise flex flex-wrap gap-3" style={{ "--i": 2 } as React.CSSProperties}>
            <Link href="/login" className={buttonStyles("gold", "lg")}>{t("home.signIn")}</Link>
            <Link href="/register" className={buttonStyles("ghost", "lg", "text-on-brand hover:bg-brand-800")}>
              {t("auth.createAccount")}
            </Link>
          </div>
        </Container>
      </section>
    </SiteShell>
  );
}
