import { ArrowLeft, ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { MarketClassCard } from "@/components/market-card";
import { SiteShell } from "@/components/shell";
import { TeacherAvatar } from "@/components/teacher-avatar";
import { market } from "@/lib/market";
import { t } from "@eduzone/lib/i18n";
import type { SubjectPage } from "@eduzone/lib/types";
import { ClassCover, Container, EmptyState, FilterChips } from "@eduzone/ui";

export async function generateMetadata({ params }: PageProps<"/[subject]">): Promise<Metadata> {
  const { subject } = (await market<SubjectPage>(`/subjects/${(await params).subject}`));
  return {
    title: `${subject.name} classes | EduZone`,
    description: t("market.subject.metaDescription", { subject: subject.name }),
  };
}

/** /<subject>: every teacher and class for one subject, filterable by exam. */
export default async function SubjectPageView({ params, searchParams }: PageProps<"/[subject]">) {
  const { subject: slug } = await params;
  const exam = (await searchParams).exam;
  const data = await market<SubjectPage>(`/subjects/${slug}`);
  const classes = typeof exam === "string" ? data.classes.filter((c) => c.exam === exam) : data.classes;
  const exams = [...new Set(data.classes.map((c) => c.exam).filter(Boolean))] as string[];

  return (
    <SiteShell bare>
      <section className="ez-grain relative overflow-hidden bg-brand-900 text-on-brand">
        <div aria-hidden className="absolute inset-y-0 right-0 hidden w-1/2 opacity-40 md:block [&_svg]:h-full">
          <ClassCover title={data.subject.name} subject={data.subject.name} size="lg" className="h-full" />
        </div>
        <Container className="relative flex flex-col gap-4 py-14 sm:py-20">
          <Link href="/classes" className="inline-flex items-center gap-1.5 self-start text-sm font-semibold text-brand-100/80 hover:text-on-brand">
            <ArrowLeft className="size-4" />
            {t("market.catalog.title")}
          </Link>
          <h1 className="ez-rise font-display text-5xl font-semibold sm:text-6xl">{data.subject.name}</h1>
          <p className="ez-rise text-lg text-brand-100/85" style={{ "--i": 1 } as React.CSSProperties}>
            {t("market.subject.counts", { classes: data.subject.class_count, teachers: data.subject.teacher_count })}
          </p>
        </Container>
      </section>

      <Container className="flex flex-col gap-12 py-12 sm:py-16">
        {data.teachers.length > 0 && (
          <section className="flex flex-col gap-4">
            <h2 className="font-display text-2xl font-semibold">{t("market.subject.teachers")}</h2>
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {data.teachers.map((tc) => (
                <li key={tc.slug}>
                  <Link href={`/${slug}/${tc.slug}`}
                        className="group flex items-center gap-4 rounded-ez-lg border border-border bg-surface p-4 shadow-ez-sm transition hover:-translate-y-0.5 hover:shadow-ez">
                    <TeacherAvatar name={tc.display_name} photo={tc.photo_url} size="lg" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-semibold">{tc.display_name}</p>
                      <p className="truncate text-sm text-muted">{tc.headline ?? t("market.teacher.classes", { count: tc.class_count })}</p>
                    </div>
                    <ChevronRight className="size-5 text-subtle group-hover:text-brand" />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="flex flex-col gap-4">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <h2 className="font-display text-2xl font-semibold">{t("market.subject.classes")}</h2>
            {exams.length > 1 && (
              <FilterChips
                items={[{ href: `/${slug}`, label: t("classes.filter.all"), active: typeof exam !== "string" },
                        ...exams.map((e) => ({ href: `/${slug}?exam=${e}`, label: t(`exam.${e}` as "exam.al"), active: exam === e }))]}
              />
            )}
          </div>
          {classes.length === 0 ? (
            <EmptyState title={t("market.subject.empty")} body={t("market.subject.emptyBody")} />
          ) : (
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {classes.map((c, i) => <MarketClassCard key={c.id} c={c} index={i} />)}
            </div>
          )}
        </section>
      </Container>
    </SiteShell>
  );
}
