import { Mail, UserRound } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import type { Schema } from "@eduzone/api-client";
import { Avatar, Badge, Card, CardTitle, DataList, ErrorText, buttonClass } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@eduzone/lib/format";
import { errorText, t, type MessageKey } from "@eduzone/lib/i18n";

import { replyToContact, updateContact } from "../../../actions";
import { NoteForm, ReplyForm, StatusButton } from "./forms";

type Detail = Schema<"ContactDetail">;

const tone = { new: "warning", open: "info", replied: "success", closed: "neutral" } as const;

/** One message as a conversation (their message, then our replies), the reply composer, and the sender's details. */
export default async function InboxMessagePage({ params }: PageProps<"/inbox/[id]">) {
  const { id } = await params;
  const res = await api<Detail>(`/platform/contact/${id}`);
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    return <ErrorText>{errorText(t, res.error)}</ErrorText>;
  }
  const m = res.data;
  const firstName = m.name.split(/\s+/)[0] ?? m.name;
  const update = updateContact.bind(null, m.id);

  return (
    <>
      <Link href="/inbox" className={`${buttonClass.link} text-sm`}>← {t("platform.inbox.back")}</Link>
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="font-display text-3xl font-semibold text-balance">{m.subject}</h1>
          <p className="mt-1.5 flex flex-wrap items-center gap-2 text-sm text-muted">
            <Badge tone={tone[m.status]}>{t(`platform.inbox.status.${m.status}`)}</Badge>
            <span className="font-mono">{m.reference}</span>
            <span>· {t(`platform.inbox.topic.${m.topic}` as MessageKey)}</span>
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <a href={`mailto:${m.email}?subject=${encodeURIComponent(`Re: ${m.subject} [${m.reference}]`)}`}
             className={buttonClass.secondary}>
            <Mail className="size-4" />{t("platform.inbox.mailto")}
          </a>
          {m.status === "closed"
            ? <StatusButton action={update} status="open" label={t("platform.inbox.reopen")} />
            : <StatusButton action={update} status="closed" label={t("platform.inbox.close")} />}
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex flex-col gap-4">
          <Bubble name={m.name} label={t("platform.inbox.wrote", { name: m.name })} at={m.created_at} body={m.message} />
          {m.reply_list.map((r) => (
            <Bubble key={r.id} name={r.author_name} label={t("platform.inbox.youReplied", { name: r.author_name })}
                    at={r.created_at} body={r.body} staff />
          ))}
          <Card>
            <ReplyForm action={replyToContact.bind(null, m.id)} email={m.email} firstName={firstName} />
          </Card>
        </div>

        <aside className="flex flex-col gap-4">
          <Card>
            <CardTitle>{t("platform.inbox.from")}</CardTitle>
            <DataList items={[
              [t("platform.inbox.from"), m.name],
              [t("platform.inbox.email"), <a key="e" href={`mailto:${m.email}`} className="break-all text-brand hover:underline">{m.email}</a>],
              [t("platform.inbox.phone"), m.phone ?? "—"],
              [t("platform.inbox.account"), m.user_id
                ? <Link key="u" href={`/users/${m.user_id}`} className="inline-flex items-center gap-1 text-brand hover:underline">
                    <UserRound className="size-3.5" />{m.user_name ?? t("platform.inbox.signedIn")}
                  </Link>
                : "—"],
              [t("platform.inbox.received"), formatDateTime(m.created_at)],
              [t("platform.inbox.earlier"), m.earlier > 0
                ? <Link key="h" href={`/inbox?filter=all&q=${encodeURIComponent(m.email)}`} className="text-brand hover:underline">
                    {t("platform.inbox.earlierLink", { count: m.earlier })}
                  </Link>
                : "0"],
            ]} />
            {m.user_agent && <p className="mt-3 text-xs break-words text-subtle">{t("platform.inbox.device")}: {m.user_agent}</p>}
          </Card>
          <Card>
            <NoteForm action={update} note={m.staff_note} />
          </Card>
        </aside>
      </div>
    </>
  );
}

function Bubble({ name, label, at, body, staff = false }: { name: string; label: string; at: string; body: string; staff?: boolean }) {
  return (
    <article className={staff ? "rounded-ez-lg border border-brand/20 bg-brand-50 p-5" : "rounded-ez-lg border border-border bg-surface p-5 shadow-ez-sm"}>
      <header className="flex items-center gap-3">
        <Avatar name={name} size="sm" />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">{label}</p>
          <p className="text-xs text-muted">{formatDateTime(at)}</p>
        </div>
      </header>
      <p className="mt-4 text-[0.9375rem] leading-relaxed whitespace-pre-wrap">{body}</p>
    </article>
  );
}
