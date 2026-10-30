import { ArrowLeft, Building2 } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { MarketClassCard } from "@/components/market-card";
import { ShareTools } from "@/components/share-tools";
import { SiteShell } from "@/components/shell";
import { market } from "@/lib/market";
import { siteOrigin } from "@/lib/site";
import { t } from "@eduzone/lib/i18n";
import type { InstitutePage } from "@eduzone/lib/types";
import { Container } from "@eduzone/ui";

export async function generateMetadata({ params }: PageProps<"/institutes/[slug]">): Promise<Metadata> {
  const { institute } = await market<InstitutePage>(`/institutes/${(await params).slug}`);
  return { title: `${institute.name} | EduZone`, description: t("market.institute.metaDescription", { name: institute.name }) };
}

/** /institutes/<slug>: an institute's teachers and classes, by subject. */
export default async function InstitutePageView({ params }: PageProps<"/institutes/[slug]">) {
  const { slug } = await params;
  const { institute, classes } = await market<InstitutePage>(`/institutes/${slug}`);
  const subjects = [...new Set(classes.map((c) => c.subject_name))];

  return (
    <SiteShell bare>
      <section className="ez-grain relative overflow-hidden bg-brand-900 text-on-brand">
        <Container className="flex flex-col gap-5 py-14 sm:py-20">
          <Link href="/institutes" className="inline-flex items-center gap-1.5 self-start text-sm font-semibold text-brand-100/80 hover:text-on-brand">
            <ArrowLeft className="size-4" />{t("market.dir.institutes")}
          </Link>
          <div className="flex items-center gap-5">
            <span className="grid size-16 place-items-center rounded-ez-lg bg-brand-800 text-gold"><Building2 className="size-8" /></span>
            <div>
              <h1 className="font-display text-4xl font-semibold sm:text-5xl">{institute.name}</h1>
              <p className="text-brand-100/80">{t("market.institute.counts", { classes: institute.class_count, teachers: institute.teacher_count })}</p>
            </div>
          </div>
          <ShareTools url={`${await siteOrigin()}/institutes/${slug}`} message={t("market.institute.shareMessage", { name: institute.name })} compact />
        </Container>
      </section>
      <Container className="flex flex-col gap-12 py-12 sm:py-16">
        {subjects.map((s) => (
          <section key={s} className="flex flex-col gap-4">
            <h2 className="font-display text-2xl font-semibold">{s}</h2>
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {classes.filter((c) => c.subject_name === s).map((c, i) => <MarketClassCard key={c.id} c={c} index={i} />)}
            </div>
          </section>
        ))}
      </Container>
    </SiteShell>
  );
}
