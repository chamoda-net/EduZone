import { ArrowRight, BookOpen, ChevronRight, CreditCard, Mail, MapPin, MessageCircleReply, PenLine, Plus, Ticket } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";

import { getMe } from "@/lib/session";
import { t, type MessageKey } from "@eduzone/lib/i18n";
import { Container, LogoMark, cx } from "@eduzone/ui";
import { SiteShell } from "@/components/shell";

import { ContactForm, CopyEmail } from "./contact-form";
import { TOPICS, type Topic } from "./topics";

export const metadata: Metadata = {
  title: `${t("static.contact.title")} | EduZone`,
  description: t("contact.meta"),
  alternates: { canonical: "/contact" },
};

const SUPPORT_EMAIL = t("about.company.emailValue");
const rise = (i: number) => ({ "--i": i }) as CSSProperties;

/** Contact: a quiet page header in the About page's family, a guide to who can help fastest beside the message form
 * (styled as an airmail letter), then quick answers. `?topic=` preselects a topic (e.g. `?topic=teaching`). */
export default async function ContactPage({ searchParams }: { searchParams: Promise<{ topic?: string }> }) {
  const [{ topic }, me] = await Promise.all([searchParams, getMe()]);
  const initial: Topic = (TOPICS as readonly string[]).includes(topic ?? "") ? (topic as Topic) : "payments";

  return (
    <SiteShell bare>
      <section className="relative isolate overflow-hidden">
        <div aria-hidden className="absolute inset-x-0 top-0 -z-10 h-[380px] bg-[linear-gradient(to_bottom,transparent_31px,rgb(26_67_49/0.06)_31px,rgb(26_67_49/0.06)_32px)] bg-[size:100%_32px] [mask-image:linear-gradient(to_bottom,black,transparent)]" />
        <div aria-hidden className="absolute -top-72 right-[-10%] -z-10 size-[720px] rounded-full bg-[radial-gradient(closest-side,rgb(212_160_63/0.14),transparent)]" />

        <Container className="pt-10 pb-10 sm:pt-14 sm:pb-14 lg:pt-16">
          <nav aria-label={t("about.breadcrumb")} className="ez-rise flex items-center gap-1.5 text-sm text-muted">
            <Link href="/" className="hover:text-foreground">{t("about.home")}</Link>
            <ChevronRight className="size-3.5 text-subtle" />
            <span className="font-semibold text-foreground" aria-current="page">{t("static.contact.title")}</span>
          </nav>
          <div className="mt-5 grid gap-8 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
            <div>
              <h1 className="ez-rise max-w-2xl font-display text-[2.2rem] leading-[1.06] font-semibold tracking-[-0.025em] text-balance sm:text-[2.9rem] lg:text-[3.5rem]"
                  style={rise(1)}>
                {t("contact.titleStart")}{" "}
                <span className="relative inline-block text-brand italic">
                  {t("contact.titleMark")}
                  <svg aria-hidden viewBox="0 0 300 14" preserveAspectRatio="none" className="absolute -bottom-1 left-0 h-2.5 w-full text-gold">
                    <path d="M2 9 C 70 2, 150 2, 298 7" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                  </svg>
                </span>
              </h1>
              <p className="ez-rise mt-5 max-w-xl text-base leading-relaxed text-muted sm:text-lg" style={rise(2)}>{t("contact.body")}</p>
            </div>
            <dl className="ez-rise grid gap-3 sm:grid-cols-2 lg:w-[30rem]" style={rise(3)}>
              <div className="flex gap-3 rounded-ez-lg border border-border bg-surface/80 p-4 shadow-ez-sm backdrop-blur">
                <Ticket className="mt-0.5 size-5 shrink-0 text-gold-strong" />
                <div className="min-w-0">
                  <dt className="text-sm font-semibold">{t("contact.ref")}</dt>
                  <dd className="mt-0.5 text-xs leading-relaxed text-muted">{t("contact.refBody")}</dd>
                </div>
              </div>
              <div className="flex gap-3 rounded-ez-lg border border-border bg-surface/80 p-4 shadow-ez-sm backdrop-blur">
                <MessageCircleReply className="mt-0.5 size-5 shrink-0 text-gold-strong" />
                <div>
                  <dt className="text-xs text-muted">{t("contact.reply")}</dt>
                  <dd className="font-display text-xl font-semibold text-brand">{t("contact.replyValue")}</dd>
                </div>
              </div>
            </dl>
          </div>
        </Container>
      </section>

      <Container className="grid grid-cols-[minmax(0,1fr)] gap-10 pb-16 sm:pb-24 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)] lg:gap-14">
        <aside className="order-2 flex flex-col gap-8 lg:order-1">
          <div>
            <Eyebrow>{t("contact.guide.eyebrow")}</Eyebrow>
            <h2 className="mt-2 font-display text-2xl font-semibold sm:text-[1.75rem]">{t("contact.guide.title")}</h2>
            <ol className="mt-6 flex flex-col">
              <Route n={1} icon={<BookOpen />} title="contact.guide.classes.title" body="contact.guide.classes.body"
                     href="/learn/classes" cta="contact.guide.classes.cta" />
              <Route n={2} icon={<CreditCard />} title="contact.guide.money.title" body="contact.guide.money.body"
                     href="#message" cta="contact.guide.money.cta" highlight />
              <Route n={3} icon={<PenLine />} title="contact.guide.teach.title" body="contact.guide.teach.body"
                     href="/teach/apply" cta="contact.guide.teach.cta" last />
            </ol>
          </div>

          <div className="rounded-[1.5rem] bg-sunken/70 p-5 sm:p-6">
            <p className="flex items-center gap-2 font-semibold"><Mail className="size-4.5 text-brand-600" />{t("contact.direct")}</p>
            <p className="mt-1.5 text-sm leading-relaxed text-muted">{t("contact.directBody")}</p>
            <div className="mt-4"><CopyEmail email={SUPPORT_EMAIL} /></div>
            <div className="mt-5 flex flex-col gap-3 border-t border-border pt-5 text-sm">
              <p className="flex items-start gap-2.5 text-muted">
                <MapPin className="mt-0.5 size-4 shrink-0 text-brand-600" />
                <span>{t("contact.companyLabel")} <span className="font-semibold text-foreground">{t("about.company.nameValue")}</span>, {t("about.company.countryValue")}</span>
              </p>
            </div>
          </div>
        </aside>

        <div id="message" className="order-1 scroll-mt-24 lg:order-2">
          <Letter>
            <h2 className="pr-20 font-display text-[1.65rem] font-semibold sm:text-3xl">{t("contact.form.title")}</h2>
            <p className="mt-1.5 pr-20 text-sm text-muted">{t("contact.form.body")}</p>
            <div className="mt-7">
              <ContactForm topic={initial} name={me?.full_name} email={me?.email ?? undefined}
                           phone={me?.phone ?? undefined} />
            </div>
          </Letter>
        </div>
      </Container>

      <Faq />
    </SiteShell>
  );
}

function Eyebrow({ children }: { children: ReactNode }) {
  return <p className="text-xs font-bold tracking-[0.14em] text-brand-600 uppercase">{children}</p>;
}

function Route({ n, icon, title, body, href, cta, highlight = false, last = false }: {
  n: number; icon: ReactNode; title: MessageKey; body: MessageKey; href: string; cta: MessageKey;
  highlight?: boolean; last?: boolean;
}) {
  return (
    <li className="relative flex gap-4 pb-7 last:pb-0">
      {!last && <span aria-hidden className="absolute top-11 bottom-1 left-[1.3rem] w-px bg-border-strong" />}
      <span className={cx("relative grid size-11 shrink-0 place-items-center rounded-full border [&>svg]:size-5",
                          highlight ? "border-brand bg-brand text-gold-300 shadow-ez" : "border-border-strong bg-surface text-brand-600")}>
        {icon}
        <span className="absolute -top-1 -right-1 grid size-5 place-items-center rounded-full bg-gold text-[0.65rem] font-bold text-brand-950">{n}</span>
      </span>
      <div className="min-w-0 pt-1">
        <p className="font-semibold">{t(title)}</p>
        <p className="mt-1 text-sm leading-relaxed text-muted">{t(body)}</p>
        <Link href={href} className="group mt-2 inline-flex items-center gap-1.5 text-sm font-semibold text-brand">
          {t(cta)}
          <ArrowRight className="size-3.5 transition group-hover:translate-x-0.5" />
        </Link>
      </div>
    </li>
  );
}

/** The form's card, dressed as an airmail letter: striped edge and a perforated stamp in the corner. */
function Letter({ children }: { children: ReactNode }) {
  return (
    <div className="ez-rise relative overflow-hidden rounded-[1.75rem] border border-border bg-surface shadow-ez-lg" style={rise(4)}>
      <div aria-hidden className="h-2 bg-[repeating-linear-gradient(-45deg,var(--ez-brand-700)_0_14px,transparent_14px_22px,var(--ez-gold-500)_22px_36px,transparent_36px_44px)]" />
      <div aria-hidden className="absolute top-7 right-6 rotate-6 sm:top-8 sm:right-8">
        <div className="bg-[radial-gradient(circle,transparent_3px,var(--ez-bg)_3.5px)] bg-[size:10px_10px] bg-[position:-5px_-5px] p-[5px] drop-shadow-[0_2px_4px_rgb(20_32_26/0.15)]">
          <div className="ez-grain flex h-[4.5rem] w-[3.75rem] flex-col items-center justify-between bg-brand-900 px-1 py-2 text-on-brand">
            <LogoMark className="h-8" />
            <span className="text-center text-[0.5rem] leading-tight font-bold tracking-[0.18em] uppercase">Sri Lanka</span>
          </div>
        </div>
      </div>
      <div className="relative p-5 sm:p-8 lg:p-10">{children}</div>
    </div>
  );
}

function Faq() {
  const items = [1, 2, 3, 4, 5] as const;
  return (
    <section className="border-t border-border bg-surface">
      <Container className="grid grid-cols-[minmax(0,1fr)] gap-8 py-16 sm:py-20 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)] lg:gap-14">
        <div>
          <Eyebrow>{t("contact.faq.eyebrow")}</Eyebrow>
          <h2 className="mt-2 font-display text-[1.9rem] leading-tight font-semibold sm:text-4xl">{t("contact.faq.title")}</h2>
          <Link href="/refund-policy" className="group mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-brand">
            {t("contact.faq.policy")}
            <ArrowRight className="size-3.5 transition group-hover:translate-x-0.5" />
          </Link>
        </div>
        <div className="divide-y divide-border border-y border-border">
          {items.map((i) => (
            <details key={i} className="group py-1" name="contact-faq">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 font-semibold [&::-webkit-details-marker]:hidden">
                {t(`contact.faq.q${i}` as MessageKey)}
                <span className="grid size-8 shrink-0 place-items-center rounded-full border border-border-strong text-brand transition group-open:rotate-45 group-open:border-brand group-open:bg-brand group-open:text-on-brand">
                  <Plus className="size-4" />
                </span>
              </summary>
              <p className="max-w-2xl pb-5 text-sm leading-relaxed text-muted">{t(`contact.faq.a${i}` as MessageKey)}</p>
            </details>
          ))}
        </div>
      </Container>
    </section>
  );
}
