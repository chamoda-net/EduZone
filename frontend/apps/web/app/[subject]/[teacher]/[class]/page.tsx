import { ArrowRight, ChevronRight, FileText, Lock, MonitorPlay, ShieldCheck, Video } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { ShareTools } from "@/components/share-tools";
import { SiteShell } from "@/components/shell";
import { TeacherAvatar } from "@/components/teacher-avatar";
import { classMeta, priceParts } from "@/lib/catalog";
import { jsonLd, market } from "@/lib/market";
import { getMe } from "@/lib/session";
import { siteOrigin } from "@/lib/site";
import { formatDateTime, formatMoney, formatMonth } from "@eduzone/lib/format";
import { t } from "@eduzone/lib/i18n";
import type { LessonType, MarketClassDetail, MarketLesson, MarketMonth } from "@eduzone/lib/types";
import { Badge, ClassCover, Container, StatusPill, buttonStyles, type PillState } from "@eduzone/ui";

type Params = { subject: string; teacher: string; class: string };

async function load(params: Promise<Params>): Promise<{ p: Params; d: MarketClassDetail }> {
  const p = await params;
  return { p, d: await market<MarketClassDetail>(`/classes/${p.subject}/${p.teacher}/${p.class}`) };
}

export async function generateMetadata({ params }: PageProps<"/[subject]/[teacher]/[class]">): Promise<Metadata> {
  const { d } = await load(params);
  const title = t("market.class.metaTitle", { title: d.class.title, teacher: d.teacher.display_name });
  const description = d.description?.slice(0, 160) ?? t("market.class.metaDescription", { subject: d.class.subject_name, teacher: d.teacher.display_name });
  return { title, description, openGraph: { title, description } };
}

const monthPill: Record<string, PillState> = { open: "unpaid", upcoming: "upcoming", closed: "closed" };
const lessonIcon: Record<LessonType, React.ReactNode> = { live: <Video />, recorded: <MonitorPlay />, document: <FileText /> };
const shortMonth = new Intl.DateTimeFormat("en", { month: "short", timeZone: "UTC" });

/** /<subject>/<teacher>/<class>: the public class page. Joining and paying happen in the student area. */
export default async function MarketClassPage({ params }: PageProps<"/[subject]/[teacher]/[class]">) {
  const { p, d } = await load(params);
  const c = d.class;
  const me = await getMe();
  const learnHref = `/learn/classes/${c.id}`;
  const url = `${await siteOrigin()}${c.path}`;
  const price = priceParts(t, { pricing_model: c.pricing_model, monthly_fee_cents: c.open_month_fee_cents ?? c.monthly_fee_cents,
                                one_time_price_cents: c.one_time_price_cents, currency: c.currency });
  const byMonth = groupLessons(d.lessons, d.months);

  return (
    <SiteShell bare>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={jsonLd({
          "@context": "https://schema.org", "@type": "Course", name: c.title, url,
          description: d.description ?? undefined, inLanguage: c.medium ?? undefined,
          provider: { "@type": "Person", name: d.teacher.display_name, url: `${await siteOrigin()}/${p.subject}/${p.teacher}` },
          offers: { "@type": "Offer", price: ((c.open_month_fee_cents ?? c.monthly_fee_cents ?? c.one_time_price_cents ?? 0) / 100).toFixed(2),
                    priceCurrency: c.currency, category: c.pricing_model === "monthly" ? "Monthly fee" : "One-time" },
        })}
      />
      <div className="bg-[linear-gradient(to_bottom,var(--ez-sunken),transparent_520px)]">
        <Container className="grid gap-x-14 gap-y-10 py-8 sm:py-12 lg:grid-cols-[1fr_360px] [&>*]:min-w-0">
          <div className="flex flex-col gap-5 lg:col-start-1">
            <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-1 text-sm font-semibold text-muted">
              <Link href={`/${c.subject_slug}`} className="hover:text-foreground">{c.subject_name}</Link>
              <ChevronRight className="size-3.5" />
              <Link href={`/${c.subject_slug}/${c.teacher_slug}`} className="hover:text-foreground">{c.teacher_name}</Link>
            </nav>
            <p className="ez-rise text-xs font-bold tracking-[0.14em] text-brand-600 uppercase">
              {classMeta(t, { subject: c.subject_name, exam: c.exam, batch_year: c.batch_year, medium: c.medium })}
            </p>
            <h1 className="ez-rise font-display text-4xl leading-[1.05] font-semibold sm:text-5xl" style={{ "--i": 1 } as React.CSSProperties}>
              {c.title}
            </h1>
            <Link href={`/${c.subject_slug}/${c.teacher_slug}`} className="ez-rise group flex items-center gap-3 self-start" style={{ "--i": 2 } as React.CSSProperties}>
              <TeacherAvatar name={d.teacher.display_name} photo={d.teacher.photo_url} />
              <div>
                <p className="font-semibold group-hover:underline">
                  {d.teacher.display_name}
                  {c.org_type === "institute" && <span className="font-normal text-muted"> · {c.org_name}</span>}
                </p>
                {d.teacher.headline && <p className="text-sm text-muted">{d.teacher.headline}</p>}
              </div>
            </Link>
            {d.description && (
              <p className="ez-rise max-w-2xl text-[1.0625rem] leading-relaxed whitespace-pre-line text-foreground/85" style={{ "--i": 3 } as React.CSSProperties}>
                {d.description}
              </p>
            )}
          </div>

          <aside className="ez-rise lg:col-start-2 lg:row-span-2 lg:row-start-1" style={{ "--i": 2 } as React.CSSProperties}>
            <div className="overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-lg lg:sticky lg:top-24">
              <ClassCover title={c.title} subject={c.subject_name} imageUrl={c.cover_image_url} label={c.exam ? t(`exam.${c.exam}`) : null} />
              <div className="flex flex-col gap-4 p-5">
                <p className="flex items-baseline gap-1.5">
                  <span className="font-display text-3xl font-semibold tabular-nums">{price.amount}</span>
                  {price.unit && <span className="text-muted">{price.unit}</span>}
                </p>
                {c.open_month_start && (
                  <p className="text-sm font-semibold text-gold-strong">{t("market.card.joinMonth", { month: formatMonth(c.open_month_start) })}</p>
                )}
                <Link href={me ? learnHref : `/login?next=${encodeURIComponent(learnHref)}`} className={buttonStyles("primary", "lg", "w-full")}>
                  {me ? t("market.class.joinOrPay") : t("class.signInToJoin")}
                  <ArrowRight className="size-4.5" />
                </Link>
                {!me && (
                  <Link href={`/register?next=${encodeURIComponent(learnHref)}`} className="text-center text-sm font-semibold text-brand hover:underline">
                    {t("auth.createAccount")}
                  </Link>
                )}
                <ul className="flex flex-col gap-2 border-t border-border pt-4 text-sm text-muted">
                  <li className="flex gap-2"><ShieldCheck className="mt-0.5 size-4 shrink-0 text-brand-600" />{t("class.trust.secure")}</li>
                  {c.pricing_model === "monthly" && (
                    <li className="flex gap-2"><Lock className="mt-0.5 size-4 shrink-0 text-brand-600" />{t("class.trust.monthly")}</li>
                  )}
                </ul>
                <div className="border-t border-border pt-4">
                  <ShareTools url={url} message={t("market.class.shareMessage", { title: c.title, teacher: d.teacher.display_name })} compact />
                </div>
              </div>
            </div>
          </aside>

          <div className="flex flex-col gap-12 lg:col-start-1 lg:row-start-2">
            {d.months.length > 0 && (
              <section className="flex flex-col gap-4">
                <div>
                  <h2 className="font-display text-2xl font-semibold">{t("class.months")}</h2>
                  <p className="text-sm text-muted">{t("class.monthsHint")}</p>
                </div>
                <ul className="flex flex-col gap-3">
                  {d.months.map((m, i) => <MonthRow key={m.id} m={m} i={i} />)}
                </ul>
              </section>
            )}
            <section className="flex flex-col gap-4">
              <h2 className="font-display text-2xl font-semibold">{t("class.lessons")}</h2>
              {byMonth.map((g) => (
                <div key={g.key} className="overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-sm">
                  {g.label && <h3 className="border-b border-border bg-sunken/50 px-5 py-3 text-sm font-bold tracking-wide text-muted">{g.label}</h3>}
                  <ul className="divide-y divide-border">
                    {g.lessons.map((l) => (
                      <li key={l.id} className="flex items-center gap-4 px-5 py-4">
                        <span className="grid size-10 shrink-0 place-items-center rounded-ez bg-sunken text-subtle [&>svg]:size-4.5">{lessonIcon[l.lesson_type]}</span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-semibold">{l.title}</span>
                          <span className="block text-sm text-muted">
                            {[t(`lessons.type.${l.lesson_type}`), l.scheduled_at && formatDateTime(l.scheduled_at)].filter(Boolean).join(" · ")}
                          </span>
                        </span>
                        {l.is_free_preview ? (
                          <Link href={me ? `/learn/lessons/${l.id}` : `/login?next=${encodeURIComponent(`/learn/lessons/${l.id}`)}`}>
                            <Badge tone="gold">{t("class.freePreview")}</Badge>
                          </Link>
                        ) : (
                          <Lock className="size-4 shrink-0 text-subtle" aria-label={t("class.locked")} />
                        )}
                      </li>
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

function MonthRow({ m, i }: { m: MarketMonth; i: number }) {
  const date = new Date(m.month_start);
  return (
    <li className="ez-rise flex items-center gap-4 rounded-ez-lg border border-border bg-surface p-4 shadow-ez-sm" style={{ "--i": i } as React.CSSProperties}>
      <div className="grid size-14 shrink-0 place-items-center rounded-ez bg-brand-900 text-center leading-none text-on-brand">
        <span>
          <span className="block text-[0.7rem] font-bold tracking-widest uppercase opacity-80">{shortMonth.format(date)}</span>
          <span className="block font-display text-lg font-semibold">{date.getUTCFullYear()}</span>
        </span>
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{formatMonth(m.month_start)}</p>
        <p className="text-sm text-muted tabular-nums">{m.fee_cents !== null ? formatMoney(m.fee_cents, m.currency) : "—"}</p>
      </div>
      <StatusPill state={monthPill[m.status] ?? "closed"}>{t(`market.class.month.${m.status}` as "market.class.month.open")}</StatusPill>
    </li>
  );
}

function groupLessons(lessons: MarketLesson[], months: MarketMonth[]) {
  const groups = months.map((m) => ({ key: m.id, label: formatMonth(m.month_start) as string | null,
                                       lessons: lessons.filter((l) => l.class_month_id === m.id) }));
  const loose = lessons.filter((l) => !l.class_month_id);
  return [...(loose.length ? [{ key: "class", label: null, lessons: loose }] : []), ...groups.filter((g) => g.lessons.length)];
}
