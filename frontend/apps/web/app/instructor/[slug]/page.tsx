import { Star } from "lucide-react";
import type { Metadata } from "next";

import type { Schema } from "@eduzone/api-client";
import { CourseCard } from "@/components/course-card";
import { MarketClassCard } from "@/components/market-card";
import { ShareTools } from "@/components/share-tools";
import { SiteShell } from "@/components/shell";
import { TeacherAvatar } from "@/components/teacher-avatar";
import { jsonLd, market } from "@/lib/market";
import { siteOrigin } from "@/lib/site";
import { t } from "@eduzone/lib/i18n";
import type { MarketClass } from "@eduzone/lib/types";
import { Container } from "@eduzone/ui";

type Page = Schema<"InstructorPage">;

const load = async (params: Promise<{ slug: string }>) => market<Page>(`/instructors/${(await params).slug}`);

export async function generateMetadata({ params }: PageProps<"/instructor/[slug]">): Promise<Metadata> {
  const { instructor: i } = await load(params);
  const title = t("market.instructor.metaTitle", { name: i.display_name });
  const description = i.headline ?? i.bio?.slice(0, 160) ?? undefined;
  return { title, description, openGraph: { title, description, images: i.photo_url ? [i.photo_url] : undefined } };
}

/** /instructor/<slug>: one page per person, with every course and tuition class they teach on EduZone. */
export default async function InstructorPage({ params }: PageProps<"/instructor/[slug]">) {
  const { instructor: i, courses, classes } = await load(params);
  const url = `${await siteOrigin()}/instructor/${i.slug}`;
  const stats = [
    { label: t("market.instructor.stat.students"), value: i.students.toLocaleString("en") },
    ...(i.course_count > 0 ? [{ label: t("market.instructor.stat.courses"), value: String(i.course_count) }] : []),
    ...(i.class_count > 0 ? [{ label: t("market.instructor.stat.classes"), value: String(i.class_count) }] : []),
    ...(i.rating_avg != null ? [{ label: t("market.instructor.stat.rating"), value: i.rating_avg.toFixed(1) }] : []),
  ];

  return (
    <SiteShell bare>
      <script type="application/ld+json" dangerouslySetInnerHTML={jsonLd({
        "@context": "https://schema.org", "@type": "Person", name: i.display_name, url, image: i.photo_url ?? undefined,
        description: i.headline ?? undefined, jobTitle: "Instructor",
      })} />
      <section className="ez-grain relative bg-brand-900 text-on-brand">
        <Container className="flex flex-col gap-8 py-12 sm:flex-row sm:items-center sm:py-16">
          <TeacherAvatar name={i.display_name} photo={i.photo_url ?? null} size="xl" className="ring-brand-800" />
          <div className="flex min-w-0 flex-col gap-3">
            <p className="text-xs font-bold tracking-[0.14em] text-gold uppercase">{t("market.instructor.eyebrow")}</p>
            <h1 className="font-display text-4xl leading-tight font-semibold sm:text-5xl">{i.display_name}</h1>
            {i.headline && <p className="text-lg text-brand-100/90">{i.headline}</p>}
            <dl className="mt-2 flex flex-wrap gap-x-8 gap-y-3">
              {stats.map((s) => (
                <div key={s.label}>
                  <dt className="text-xs font-semibold tracking-wide text-brand-100/70 uppercase">{s.label}</dt>
                  <dd className="flex items-center gap-1 font-display text-2xl font-semibold tabular-nums">
                    {s.value}
                    {s.label === t("market.instructor.stat.rating") && <Star className="size-4 fill-gold text-gold" />}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </Container>
      </section>

      <Container className="grid gap-10 py-10 lg:grid-cols-[1fr_300px] [&>*]:min-w-0">
        <div className="flex flex-col gap-12">
          {i.bio && (
            <section>
              <h2 className="mb-3 font-display text-2xl font-semibold">{t("market.instructor.about")}</h2>
              <p className="max-w-3xl text-[0.9375rem] leading-relaxed whitespace-pre-line text-foreground/85">{i.bio}</p>
              {i.highlights.length > 0 && (
                <ul className="mt-4 flex flex-wrap gap-2">
                  {i.highlights.map((h) => <li key={h} className="rounded-full bg-gold/15 px-3 py-1 text-sm font-medium text-gold-strong">{h}</li>)}
                </ul>
              )}
            </section>
          )}
          {courses.length > 0 && (
            <section className="flex flex-col gap-5">
              <h2 className="font-display text-2xl font-semibold">
                {t("market.instructor.courses")} <span className="text-base font-normal text-muted">({courses.length})</span>
              </h2>
              <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
                {courses.map((c, n) => <CourseCard key={c.id} c={c} index={n} />)}
              </div>
            </section>
          )}
          {classes.length > 0 && (
            <section className="flex flex-col gap-5">
              <h2 className="font-display text-2xl font-semibold">
                {t("market.instructor.classes")} <span className="text-base font-normal text-muted">({classes.length})</span>
              </h2>
              <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
                {classes.map((c, n) => <MarketClassCard key={c.id} c={c as unknown as MarketClass} index={n} />)}
              </div>
            </section>
          )}
        </div>
        <aside className="flex flex-col gap-4">
          <div className="rounded-ez-lg border border-border bg-surface p-5 shadow-ez-sm lg:sticky lg:top-24">
            <ShareTools url={url} message={i.display_name} />
          </div>
        </aside>
      </Container>
    </SiteShell>
  );
}
