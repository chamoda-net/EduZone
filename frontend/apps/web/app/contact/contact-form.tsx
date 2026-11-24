"use client";

import {
  ArrowRight, BookOpen, Building2, Check, CircleHelp, Copy, CreditCard, GraduationCap, Handshake, Info, MailCheck,
  PenLine, ShieldAlert, UserRound,
} from "lucide-react";
import Link from "next/link";
import { useActionState, useState, type ReactNode } from "react";

import type { MessageKey } from "@eduzone/lib/i18n";
import { useT } from "@eduzone/lib/i18n/client";
import { Button, ErrorText, Field, Input, Textarea, buttonStyles, cx, toast } from "@eduzone/ui";

import { sendContact, type ContactState } from "./actions";
import { TOPICS, type Topic } from "./topics";


const ICONS: Record<Topic, ReactNode> = {
  payments: <CreditCard />, account: <UserRound />, classes: <BookOpen />, courses: <GraduationCap />,
  teaching: <PenLine />, institutes: <Building2 />, partnership: <Handshake />, other: <CircleHelp />,
};

/** The letter: a topic picked from chips (with a tip for each), the sender's details, the message. After sending,
 * the card turns into a receipt with the reference. */
export function ContactForm({ topic: initialTopic, name, email, phone }: {
  topic: Topic; name?: string; email?: string; phone?: string;
}) {
  const t = useT();
  const [state, submit, pending] = useActionState<ContactState, FormData>(sendContact, {});
  const [topic, setTopic] = useState<Topic>(initialTopic);
  const [length, setLength] = useState(0);
  // 'Send another' dismisses the receipt; the next message has a new reference, so its receipt shows again.
  const [dismissed, setDismissed] = useState<string | null>(null);
  const sent = state.sent && state.reference !== dismissed ? state : null;
  const values = !state.sent ? state.values : undefined;

  if (sent) {
    return (
      <Sent reference={sent.reference} name={sent.name} email={sent.email}
            onAgain={() => { setDismissed(sent.reference); setLength(0); }} />
    );
  }

  return (
    <form action={submit} className="flex flex-col gap-6" key={dismissed ?? ""}>
      <fieldset className="flex flex-col gap-3">
        <legend className="mb-3 text-sm font-semibold text-foreground">{t("contact.form.topic")}</legend>
        <div className="flex flex-wrap gap-2">
          {TOPICS.map((key) => (
            <label key={key}
                   className={cx(
                     "group inline-flex cursor-pointer items-center gap-2 rounded-full border px-3.5 py-2 text-sm font-medium transition",
                     "has-[:focus-visible]:ring-4 has-[:focus-visible]:ring-brand/15 [&_svg]:size-4",
                     topic === key
                       ? "border-brand bg-brand text-on-brand shadow-ez-sm [&_svg]:text-gold-300"
                       : "border-border-strong bg-surface text-foreground hover:border-brand/50 hover:bg-brand-50 [&_svg]:text-brand-600",
                   )}>
              <input type="radio" name="topic" value={key} checked={topic === key} onChange={() => setTopic(key)}
                     className="sr-only" />
              {ICONS[key]}
              {t(`contact.topic.${key}` as MessageKey)}
            </label>
          ))}
        </div>
        <p key={topic} aria-live="polite"
           className="ez-rise flex gap-2.5 rounded-ez border border-gold/30 bg-gold-100/70 px-3.5 py-3 text-sm leading-relaxed text-foreground">
          <Info className="mt-0.5 size-4 shrink-0 text-gold-strong" />
          <span>
            {t(`contact.hint.${topic}` as MessageKey)}
            {topic === "teaching" && (
              <> <Link href="/teach/apply" className="font-semibold text-brand underline-offset-2 hover:underline">
                {t("contact.guide.teach.cta")}
              </Link></>
            )}
          </span>
        </p>
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("contact.form.name")}>
          <Input name="name" autoComplete="name" required minLength={2} maxLength={120}
                 defaultValue={values?.name ?? name} />
        </Field>
        <Field label={t("contact.form.email")} hint={t("contact.form.emailHint")}>
          <Input name="email" type="email" autoComplete="email" required maxLength={254}
                 defaultValue={values?.email ?? email} />
        </Field>
      </div>
      <Field label={t("contact.form.phone")} optional={t("contact.form.optional")} hint={t("contact.form.phoneHint")}>
        <Input name="phone" type="tel" inputMode="tel" autoComplete="tel" maxLength={20} placeholder="077 123 4567"
               defaultValue={values?.phone ?? phone} className="sm:max-w-xs" />
      </Field>
      <Field label={t("contact.form.subject")}>
        <Input name="subject" required minLength={3} maxLength={150} placeholder={t("contact.form.subjectPlaceholder")}
               defaultValue={values?.subject} />
      </Field>
      <div className="flex flex-col gap-1.5">
        <Field label={t("contact.form.message")}>
          <Textarea name="message" required minLength={10} maxLength={5000} rows={6}
                    placeholder={t("contact.form.messagePlaceholder")} defaultValue={values?.message}
                    onChange={(e) => setLength(e.currentTarget.value.length)} className="min-h-40 resize-y" />
        </Field>
        <span className={cx("self-end text-xs tabular-nums", length > 4800 ? "text-warning" : "text-subtle")}>
          {t("contact.form.count", { count: length })}
        </span>
      </div>

      {/* Honeypot: hidden from people and screen readers; bots that fill every field give themselves away. */}
      <div aria-hidden className="absolute -left-[9999px] h-px w-px overflow-hidden">
        <label>{t("contact.form.honeypot")}<input name="website" tabIndex={-1} autoComplete="off" /></label>
      </div>

      <p className="flex gap-2.5 text-xs leading-relaxed text-muted">
        <ShieldAlert className="size-4 shrink-0 text-brand-600" />
        {t("contact.form.safety")}
      </p>
      <ErrorText>{!state.sent ? state.error : undefined}</ErrorText>
      <Button size="lg" loading={pending} iconRight={<ArrowRight className="size-4.5" />} className="sm:self-start">
        {t("contact.form.send")}
      </Button>
    </form>
  );
}

function Sent({ reference, name, email, onAgain }: { reference: string; name: string; email: string; onAgain: () => void }) {
  const t = useT();
  return (
    <div className="ez-rise flex flex-col items-center py-4 text-center" role="status">
      <span className="relative grid size-16 place-items-center rounded-full bg-success-bg text-success">
        <span aria-hidden className="absolute inset-0 animate-ping rounded-full bg-success/15 [animation-iteration-count:2]" />
        <MailCheck className="size-7" />
      </span>
      <h3 className="mt-5 font-display text-3xl font-semibold">{t("contact.sent.title")}</h3>
      <p className="mt-2 max-w-sm text-muted">{t("contact.sent.body", { name, email })}</p>

      {/* The reference as a torn ticket stub. */}
      <div className="relative mt-7 w-full max-w-sm rounded-ez-lg border border-dashed border-gold bg-gold-100/60 px-6 py-5">
        <span aria-hidden className="absolute top-1/2 -left-2.5 size-5 -translate-y-1/2 rounded-full border border-dashed border-gold bg-surface [clip-path:inset(0_0_0_50%)]" />
        <span aria-hidden className="absolute top-1/2 -right-2.5 size-5 -translate-y-1/2 rounded-full border border-dashed border-gold bg-surface [clip-path:inset(0_50%_0_0)]" />
        <p className="text-xs font-bold tracking-[0.14em] text-gold-strong uppercase">{t("contact.sent.reference")}</p>
        <div className="mt-2 flex items-center justify-center gap-3">
          <span className="font-mono text-2xl font-semibold tracking-[0.12em] text-brand-950">{reference}</span>
          <button type="button" aria-label={t("contact.copy")} title={t("contact.copy")}
                  onClick={async () => {
                    try { await navigator.clipboard.writeText(reference); toast(t("contact.copied")); } catch { /* ignore */ }
                  }}
                  className="grid size-9 place-items-center rounded-full text-brand hover:bg-gold-100">
            <Copy className="size-4" />
          </button>
        </div>
      </div>

      <div className="mt-7 w-full max-w-sm text-left">
        <p className="text-sm font-semibold">{t("contact.sent.next")}</p>
        <ol className="mt-3 flex flex-col gap-3">
          {(["contact.sent.step1", "contact.sent.step2", "contact.sent.step3"] as const).map((key, i) => (
            <li key={key} className="flex gap-3 text-sm text-muted">
              <span className="grid size-6 shrink-0 place-items-center rounded-full bg-brand-50 text-xs font-bold text-brand">
                {i === 0 ? <Check className="size-3.5" /> : i + 1}
              </span>
              {t(key)}
            </li>
          ))}
        </ol>
      </div>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Button variant="secondary" onClick={onAgain}>{t("contact.sent.again")}</Button>
        <Link href="/classes" className={buttonStyles("ghost")}>{t("contact.sent.browse")}</Link>
      </div>
    </div>
  );
}

/** The support address with a copy button. */
export function CopyEmail({ email }: { email: string }) {
  const t = useT();
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex items-center gap-2 rounded-ez border border-border bg-surface py-1.5 pr-1.5 pl-3.5">
      <a href={`mailto:${email}`} className="min-w-0 flex-1 truncate text-sm font-semibold text-brand hover:underline">{email}</a>
      <button type="button"
              onClick={async () => {
                try { await navigator.clipboard.writeText(email); setCopied(true); setTimeout(() => setCopied(false), 1800); } catch { /* ignore */ }
              }}
              className={buttonStyles("secondary", "sm", "shrink-0")}>
        {copied ? <Check className="size-4 text-success" /> : <Copy className="size-4" />}
        {copied ? t("contact.copied") : t("contact.copy")}
      </button>
    </div>
  );
}
