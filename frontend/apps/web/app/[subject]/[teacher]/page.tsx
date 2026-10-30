import { Award, BookOpen, ChevronRight, Users } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { MarketClassCard } from "@/components/market-card";
import { ShareTools } from "@/components/share-tools";
import { SiteShell } from "@/components/shell";
import { TeacherAvatar } from "@/components/teacher-avatar";
import { jsonLd, market } from "@/lib/market";
import { siteOrigin } from "@/lib/site";
import { t } from "@eduzone/lib/i18n";
import type { TeacherPage } from "@eduzone/lib/types";
import { Badge, Container, buttonStyles } from "@eduzone/ui";

type Params = { subject: string; teacher: string };

async function load(params: Promise<Params>): Promise<{ p: Params; data: TeacherPage }> {
  const p = await params;
  return { p, data: await market<TeacherPage>(`/teachers/${p.teacher}?subject=${encodeURIComponent(p.subject)}`) };
}

export async function generateMetadata({ params }: PageProps<"/[subject]/[teacher]">): Promise<Metadata> {
  const { data } = await load(params);
  const subject = data.subject?.name ?? "";
  const title = t("market.teacher.metaTitle", { name: data.teacher.display_name, subject });
  const description = data.teacher.headline ?? t("market.teacher.metaDescription", { name: data.teacher.display_name, subject });
  return { title, description, openGraph: { title, description, type: "profile" } };
}

/** /<subject>/<teacher>: the page a teacher shares on WhatsApp, Facebook and posters. */
export default async function TeacherPageView({ params }: PageProps<"/[subject]/[teacher]">) {
  const { p, data } = await load(params);
  const { teacher, subject } = data;
  const url = `${await siteOrigin()}/${p.subject}/${p.teacher}`;
  const firstOpen = data.classes.find((c) => c.open_month_start);

  return (
    <SiteShell bare>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={jsonLd({
          "@context": "https://schema.org", "@type": "Person", name: teacher.display_name, url,
          jobTitle: teacher.headline ?? undefined, description: teacher.bio ?? undefined,
          image: teacher.photo_url ?? undefined, knowsAbout: teacher.subjects.map((s) => s.name),
        })}
      />
      <section className="border-b border-border bg-[linear-gradient(to_bottom,var(--ez-sunken),transparent)]">
        <Container className="flex flex-col items-center gap-6 py-12 text-center sm:py-16 md:flex-row md:items-end md:text-left">
          <TeacherAvatar name={teacher.display_name} photo={teacher.photo_url} size="xl" className="ez-rise" />
          <div className="flex min-w-0 flex-1 flex-col items-center gap-3 md:items-start">
            <p className="ez-rise text-xs font-bold tracking-[0.14em] text-brand-600 uppercase">
              {t("market.teacher.eyebrow", { subject: subject?.name ?? "" })}
            </p>
            <h1 className="ez-rise font-display text-4xl leading-tight font-semibold sm:text-5xl" style={{ "--i": 1 } as React.CSSProperties}>
              {teacher.display_name}
            </h1>
            {teacher.headline && <p className="ez-rise text-lg text-muted" style={{ "--i": 2 } as React.CSSProperties}>{teacher.headline}</p>}
            <div className="ez-rise flex flex-wrap justify-center gap-2 md:justify-start" style={{ "--i": 3 } as React.CSSProperties}>
              {teacher.subjects.map((s) => (
                <Link key={s.slug} href={`/${s.slug}/${teacher.slug}`}>
                  <Badge tone={s.slug === subject?.slug ? "brand" : "neutral"}>{s.name}</Badge>
                </Link>
              ))}
              {teacher.mediums.map((m) => <Badge key={m} tone="neutral">{t(`medium.${m}` as "medium.si")}</Badge>)}
            </div>
            <div className="ez-rise flex flex-wrap items-center justify-center gap-x-5 gap-y-1 text-sm text-muted md:justify-start" style={{ "--i": 4 } as React.CSSProperties}>
              <span className="inline-flex items-center gap-1.5"><BookOpen className="size-4" />{t("market.teacher.classes", { count: teacher.class_count })}</span>
              {teacher.students > 0 && (
                <span className="inline-flex items-center gap-1.5"><Users className="size-4" />{t("market.card.students", { count: teacher.students })}</span>
              )}
            </div>
          </div>
          <div className="ez-rise flex flex-col items-center gap-3 md:items-end" style={{ "--i": 3 } as React.CSSProperties}>
            <a href="#classes" className={buttonStyles("primary", "lg")}>
              {firstOpen?.open_month_start
                ? t("market.teacher.joinMonth", { month: new Date(firstOpen.open_month_start).toLocaleString("en", { month: "long", timeZone: "UTC" }) })
                : t("market.teacher.viewClasses")}
            </a>
            <ShareTools url={url} message={t("market.teacher.shareMessage", { name: teacher.display_name, subject: subject?.name ?? "" })} compact />
          </div>
        </Container>
      </section>

      <Container className="grid gap-12 py-12 sm:py-16 lg:grid-cols-[1fr_320px] [&>*]:min-w-0">
        <section id="classes" className="flex scroll-mt-24 flex-col gap-5">
          <h2 className="font-display text-2xl font-semibold">
            {t("market.teacher.classesIn", { subject: subject?.name ?? "" })}
          </h2>
          <div className="grid gap-5 sm:grid-cols-2">
            {data.classes.map((c, i) => <MarketClassCard key={c.id} c={c} index={i} />)}
          </div>
        </section>

        <aside className="flex flex-col gap-6">
          {teacher.highlights.length > 0 && (
            <div className="rounded-ez-lg border border-gold/30 bg-gold-100/60 p-5">
              <h2 className="mb-3 font-display text-lg font-semibold">{t("market.teacher.highlights")}</h2>
              <ul className="flex flex-col gap-2.5">
                {teacher.highlights.map((h) => (
                  <li key={h} className="flex gap-2.5 text-sm">
                    <Award className="mt-0.5 size-4 shrink-0 text-gold-strong" />
                    {h}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {teacher.bio && (
            <div className="rounded-ez-lg border border-border bg-surface p-5 shadow-ez-sm">
              <h2 className="mb-2 font-display text-lg font-semibold">{t("market.teacher.about")}</h2>
              <p className="text-sm leading-relaxed whitespace-pre-line text-foreground/85">{teacher.bio}</p>
            </div>
          )}
          {data.other_subjects.length > 0 && (
            <div className="rounded-ez-lg border border-border bg-surface p-5 shadow-ez-sm">
              <h2 className="mb-2 font-display text-lg font-semibold">{t("market.teacher.otherSubjects")}</h2>
              <ul className="flex flex-col">
                {data.other_subjects.map((s) => (
                  <li key={s.slug}>
                    <Link href={`/${s.slug}/${teacher.slug}`} className="flex items-center justify-between py-2 text-sm font-semibold text-brand hover:underline">
                      {s.name}
                      <ChevronRight className="size-4" />
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </Container>
    </SiteShell>
  );
}
