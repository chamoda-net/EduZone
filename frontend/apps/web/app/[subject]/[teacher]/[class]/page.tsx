import { Armchair, ArrowRight, CalendarClock, ChevronRight, FileText, Lock, MonitorPlay, PlayCircle, ShieldCheck, Video } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { AddToCartButton } from "@/components/add-to-cart";
import { ShareTools } from "@/components/share-tools";
import { SiteShell } from "@/components/shell";
import { TeacherAvatar } from "@/components/teacher-avatar";
import { getCart, inCart } from "@/lib/cart";
import { classMeta, priceParts } from "@/lib/catalog";
import { jsonLd, market } from "@/lib/market";
import { seatBadge } from "@/lib/seats";
import { getMe } from "@/lib/session";
import { siteOrigin } from "@/lib/site";
import { OG_BASE } from "@/lib/seo";
import { formatDateTime, formatMoney, formatMonth } from "@eduzone/lib/format";
import { t } from "@eduzone/lib/i18n";
import type { LessonType, MarketClassDetail, MarketLesson, MarketMonth } from "@eduzone/lib/types";
import { Badge, ClassCover, Container, StatusPill, buttonStyles, type PillState } from "@eduzone/ui";

import { JoinNowButton, LessonPreview } from "./join";

type Params = { subject: string; teacher: string; class: string };

async function load(params: Promise<Params>): Promise<{ p: Params; d: MarketClassDetail }> {
  const p = await params;
  return { p, d: await market<MarketClassDetail>(`/classes/${p.subject}/${p.teacher}/${p.class}`) };
}

export async function generateMetadata({ params }: PageProps<"/[subject]/[teacher]/[class]">): Promise<Metadata> {
  const { d } = await load(params);
  const title = t("market.class.metaTitle", { title: d.class.title, teacher: d.teacher.display_name });
  const description = d.description?.slice(0, 160) ?? t("market.class.metaDescription", { subject: d.class.subject_name, teacher: d.teacher.display_name });
  return { title, description, alternates: { canonical: d.class.path }, openGraph: { ...OG_BASE, title, description } };
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
  // What "Add to cart" adds: the open month of a monthly class, or a one-time class (free classes are joined).
  const openMonth = d.months.find((m) => m.status === "open");
  const cartMonth = c.pricing_model === "monthly" ? openMonth?.id : c.pricing_model === "one_time" ? null : undefined;
  // Full, closed or ask-first classes are not added to a cart here: the student area has the right next step.
  const blocked = c.is_full || c.registration === "closed" || c.registration === "ask";
  const cart = cartMonth !== undefined && !blocked ? await getCart() : null;
  const seat = seatBadge(c);
  const schedule = liveSchedule(d.lessons);
  const signIn = `/login?next=${encodeURIComponent(learnHref)}`;
  // The main button: buy the open month (or the one-time class) straight away; guests sign in or register in the cart.
  const joinLabel = cartMonth && openMonth
    ? t("market.class.joinMonthPrice", { month: formatMonth(openMonth.month_start), price: price.amount })
    : t("market.class.buyPrice", { price: price.amount });

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
            <div className="ez-rise flex flex-wrap items-center gap-3">
              <p className="text-xs font-bold tracking-[0.14em] text-brand-600 uppercase">
                {classMeta(t, { subject: c.subject_name, exam: c.exam, batch_year: c.batch_year, medium: c.medium })}
              </p>
              {seat && <Badge tone={seat.tone}><Armchair className="size-3" />{seat.label}</Badge>}
            </div>
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
                {c.open_month_start && !c.is_full && c.registration !== "closed" && !(cart && cartMonth !== undefined) && (
                  <p className="text-sm font-semibold text-gold-strong">{t("market.card.joinMonth", { month: formatMonth(c.open_month_start) })}</p>
                )}
                {schedule && (
                  <p className="flex items-start gap-2 text-sm font-medium">
                    <CalendarClock className="mt-0.5 size-4 shrink-0 text-brand-600" />
                    {schedule}
                  </p>
                )}
                <SeatPanel c={c} />
                {cart && cartMonth !== undefined ? (
                  inCart(cart, c.id, cartMonth) ? (
                    <Link href="/cart" className={buttonStyles("primary", "lg", "w-full")}>
                      {t("market.class.goToCart")}<ArrowRight className="size-4.5" />
                    </Link>
                  ) : (
                    <>
                      <JoinNowButton classId={c.id} monthId={cartMonth} label={joinLabel} />
                      <AddToCartButton
                        block
                        classId={c.id}
                        monthId={cartMonth}
                        label={openMonth && cartMonth ? t("cart.addMonth", { month: formatMonth(openMonth.month_start) }) : undefined}
                      />
                    </>
                  )
                ) : (
                  <Link href={me ? learnHref : signIn} className={buttonStyles("primary", "lg", "w-full")}>
                    {c.is_full || c.registration === "closed" ? t("seat.notifyMe")
                      : c.registration === "ask" ? t("seat.askButton")
                      : c.pricing_model === "free" ? t("market.class.joinFree")
                      : t("market.class.seeMonths")}
                    <ArrowRight className="size-4.5" />
                  </Link>
                )}
                <Link href={me ? learnHref : signIn} className="text-center text-sm font-semibold text-brand hover:underline">
                  {blocked && c.pricing_model === "monthly" ? t("seat.alreadyIn")
                    : me ? t("market.class.openMine") : t("market.class.signInStudent")}
                </Link>
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
                        {l.can_preview ? (
                          <LessonPreview lessonId={l.id} title={l.title}
                                         trigger={<Badge tone="gold"><PlayCircle className="size-3" />{t("market.class.preview")}</Badge>} />
                        ) : l.is_free_preview ? (
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

/** Seats of the open month (or class): how many are free when the teacher shows it, and why it can't be joined now. */
function SeatPanel({ c }: { c: MarketClassDetail["class"] }) {
  const state = c.registration == null ? null : c.is_full ? "full" : c.registration === "closed" ? "closed" : c.registration === "ask" ? "ask" : null;
  const bar = c.seat_limit != null && c.seats_left != null;
  if (!state && !bar) return null;
  return (
    <div className="flex flex-col gap-3 rounded-ez border border-border bg-sunken/50 p-3.5">
      {bar && c.seat_limit != null && c.seats_left != null && (
        <div className="flex flex-col gap-2">
          <p className="flex items-center gap-2 text-sm font-semibold tabular-nums">
            <Armchair className="size-4.5 text-brand-600" />
            {t("seat.ofSeats", { left: c.seats_left, limit: c.seat_limit })}
          </p>
          <div aria-hidden className="h-2 overflow-hidden rounded-full bg-border">
            <div className="h-full rounded-full bg-brand" style={{ width: `${Math.round(((c.seat_limit - c.seats_left) / c.seat_limit) * 100)}%` }} />
          </div>
        </div>
      )}
      {state && (
        <div className="text-sm">
          <p className="font-semibold">{t(`seat.panel.${state}`)}</p>
          <p className="leading-relaxed text-muted">{t(`seat.panel.${state}Body`)}</p>
        </div>
      )}
    </div>
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
      <div className="flex shrink-0 flex-col items-end gap-1.5">
        <StatusPill state={monthPill[m.status] ?? "closed"}>{t(`market.class.month.${m.status}` as "market.class.month.open")}</StatusPill>
        {m.status === "open" && (m.is_full ? <Badge tone="danger">{t("seat.full")}</Badge>
          : m.seats_left != null && <span className="text-xs font-semibold text-muted tabular-nums">{t("seat.left", { count: m.seats_left })}</span>)}
      </div>
    </li>
  );
}

const colomboSlot = new Intl.DateTimeFormat("en", { weekday: "long", hour: "numeric", minute: "2-digit", timeZone: "Asia/Colombo" });

/** When the class meets, from its live lessons: "Every Saturday, 8:00 AM" when one weekday and time repeats among the
 * coming (or, failing that, all) live lessons, else the next live lesson's date, else nothing. */
function liveSchedule(lessons: MarketLesson[]): string | null {
  const live = lessons.filter((l) => l.lesson_type === "live" && l.scheduled_at)
                      .sort((a, b) => (a.scheduled_at as string).localeCompare(b.scheduled_at as string));
  if (live.length === 0) return null;
  const now = Date.now();
  const coming = live.filter((l) => new Date(l.scheduled_at as string).getTime() >= now);
  const counts = new Map<string, { day: string; time: string; n: number }>();
  for (const l of coming.length >= 2 ? coming : live) {
    const parts = colomboSlot.formatToParts(new Date(l.scheduled_at as string));
    const day = parts.find((p) => p.type === "weekday")?.value ?? "";
    // "8:00 AM": the hour, minute and day period, without the weekday or the comma after it.
    const time = parts
      .filter((p) => p.type === "hour" || p.type === "minute" || p.type === "dayPeriod" || (p.type === "literal" && p.value.trim() !== ","))
      .map((p) => p.value).join("").trim();
    const key = `${day} ${time}`;
    counts.set(key, { day, time, n: (counts.get(key)?.n ?? 0) + 1 });
  }
  const top = [...counts.values()].sort((a, b) => b.n - a.n)[0];
  if (top && top.n >= 2) return t("market.class.weekly", { day: top.day, time: top.time });
  return coming[0]?.scheduled_at ? t("market.class.nextLive", { when: formatDateTime(coming[0].scheduled_at) }) : null;
}

function groupLessons(lessons: MarketLesson[], months: MarketMonth[]) {
  const groups = months.map((m) => ({ key: m.id, label: formatMonth(m.month_start) as string | null,
                                       lessons: lessons.filter((l) => l.class_month_id === m.id) }));
  const loose = lessons.filter((l) => !l.class_month_id);
  return [...(loose.length ? [{ key: "class", label: null, lessons: loose }] : []), ...groups.filter((g) => g.lessons.length)];
}
