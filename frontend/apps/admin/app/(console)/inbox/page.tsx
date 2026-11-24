import { Inbox, MailCheck, Search, UserRound } from "lucide-react";
import Link from "next/link";

import type { Schema } from "@eduzone/api-client";
import { Badge, EmptyState, ErrorText, FilterChips, PageHeader, buttonClass, cx } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@eduzone/lib/format";
import { errorText, t, type MessageKey } from "@eduzone/lib/i18n";

type Page = Schema<"ContactPage">;

const FILTERS = ["active", "replied", "closed", "all"] as const;
type Filter = (typeof FILTERS)[number];

const statusTone = { new: "warning", open: "info", replied: "success", closed: "neutral" } as const;

/** Messages from the Contact page, newest first. "To answer" = new and open. */
export default async function InboxPage({ searchParams }: PageProps<"/inbox">) {
  const sp = await searchParams;
  const filter: Filter = FILTERS.includes(sp.filter as Filter) ? (sp.filter as Filter) : "active";
  const q = typeof sp.q === "string" ? sp.q.trim() : "";
  const cursor = typeof sp.cursor === "string" ? sp.cursor : null;
  const params = new URLSearchParams({
    limit: "50", ...(filter !== "all" ? { status: filter } : {}), ...(q ? { q } : {}), ...(cursor ? { cursor } : {}),
  });
  const res = await api<Page>(`/platform/contact?${params}`);
  const counts = res.ok ? res.data.counts : null;
  const countOf = (f: Filter) => !counts ? undefined
    : f === "active" ? counts.new + counts.open || undefined
    : f === "all" ? undefined : counts[f] || undefined;
  const href = (f: Filter) => `/inbox?${new URLSearchParams({ ...(f !== "active" ? { filter: f } : {}), ...(q ? { q } : {}) })}`;

  return (
    <>
      <PageHeader title={t("platform.nav.inbox")} description={t("platform.inbox.body")} />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <FilterChips items={FILTERS.map((f) => ({
          href: href(f), label: t(`platform.inbox.filter.${f}`), active: f === filter, count: countOf(f),
        }))} />
        <form className="relative sm:w-80" action="/inbox">
          {filter !== "active" && <input type="hidden" name="filter" value={filter} />}
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-subtle" />
          <input name="q" defaultValue={q} placeholder={t("platform.inbox.search")} aria-label={t("platform.inbox.searchButton")}
                 className="min-h-10 w-full rounded-ez border border-border-strong bg-surface pr-3 pl-9 text-sm outline-none focus:border-brand focus:ring-4 focus:ring-brand/12" />
        </form>
      </div>
      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.items.length === 0 && (
        filter === "active" && !q
          ? <EmptyState icon={<MailCheck />} title={t("platform.inbox.emptyActive")} body={t("platform.inbox.emptyActiveBody")} />
          : <EmptyState icon={<Inbox />} title={t("platform.inbox.empty")} />
      )}
      {res.ok && res.data.items.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-ez-lg border border-border bg-surface">
          {res.data.items.map((m) => (
            <li key={m.id}>
              <Link href={`/inbox/${m.id}`}
                    className={cx("flex gap-3 p-4 hover:bg-sunken/50", m.status === "new" && "bg-gold-100/40")}>
                <span aria-hidden className={cx("mt-2 size-2 shrink-0 rounded-full", m.status === "new" ? "bg-gold" : "bg-transparent")} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                    <p className={cx("flex min-w-0 items-center gap-2", m.status === "new" ? "font-bold" : "font-semibold")}>
                      <span className="truncate">{m.name}</span>
                      {m.signed_in && <UserRound aria-label={t("platform.inbox.signedIn")} className="size-3.5 shrink-0 text-brand-600" />}
                    </p>
                    <span className="text-xs text-muted tabular-nums">{formatDateTime(m.created_at)}</span>
                  </div>
                  <p className={cx("mt-0.5 truncate text-sm", m.status === "new" ? "font-semibold text-foreground" : "text-foreground")}>
                    {m.subject}
                  </p>
                  <p className="mt-0.5 line-clamp-1 text-sm text-muted">{m.preview}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
                    <Badge tone={statusTone[m.status]}>{t(`platform.inbox.status.${m.status}`)}</Badge>
                    <span className="font-mono">{m.reference}</span>
                    <span>· {t(`platform.inbox.topic.${m.topic}` as MessageKey)}</span>
                    {m.replies > 0 && <span>· {t("platform.inbox.replies", { count: m.replies })}</span>}
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {res.ok && res.data.next_cursor && (
        <Link href={`${href(filter)}&cursor=${encodeURIComponent(res.data.next_cursor)}`} className={`${buttonClass.link} self-end`}>
          {t("classes.loadMore")}
        </Link>
      )}
    </>
  );
}
