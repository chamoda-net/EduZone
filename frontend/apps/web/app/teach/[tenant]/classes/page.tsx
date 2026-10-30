import { teachHref } from "@/lib/workspace";
import { LibraryBig, Plus } from "lucide-react";
import Link from "next/link";

import { api } from "@/lib/api";
import { classMeta, priceParts } from "@/lib/catalog";
import { errorText, t } from "@eduzone/lib/i18n";
import type { ClassPage, ClassStatus } from "@eduzone/lib/types";
import { Badge, ClassCover, EmptyState, ErrorText, FilterChips, PageHeader, buttonStyles } from "@eduzone/ui";

const FILTERS: (ClassStatus | null)[] = [null, "draft", "published", "archived"];

export default async function ClassesPage({ searchParams }: PageProps<"/teach/[tenant]/classes">) {
  const base = await teachHref();
  const sp = await searchParams;
  const status = FILTERS.includes(sp.status as ClassStatus) ? (sp.status as ClassStatus) : null;
  const cursor = typeof sp.cursor === "string" ? sp.cursor : null;

  const query = new URLSearchParams({ limit: "20" });
  if (status) query.set("status", status);
  if (cursor) query.set("cursor", cursor);
  const res = await api<ClassPage>(`~/classes?${query}`);

  const href = (s: ClassStatus | null, c?: string) => {
    const q = new URLSearchParams();
    if (s) q.set("status", s);
    if (c) q.set("cursor", c);
    return q.size ? `${base}/classes?${q}` : `${base}/classes`;
  };

  return (
    <>
      <PageHeader
        eyebrow={t("shell.console")}
        title={t("classes.title")}
        description={t("classes.subtitle")}
        actions={
          <Link href={`${base}/classes/new`} className={buttonStyles("primary")}>
            <Plus className="size-4.5" />
            {t("classes.new")}
          </Link>
        }
      />

      <FilterChips
        items={FILTERS.map((f) => ({ href: href(f), label: f ? t(`status.${f}`) : t("classes.filter.all"), active: f === status }))}
      />

      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.items.length === 0 && (
        <EmptyState
          icon={<LibraryBig />}
          title={t("classes.empty")}
          body={t("classes.emptyBody")}
          action={<Link href={`${base}/classes/new`} className={buttonStyles("primary")}>{t("classes.new")}</Link>}
        />
      )}
      {res.ok && res.data.items.length > 0 && (
        <ul className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {res.data.items.map((c, i) => {
            const price = priceParts(t, c);
            return (
              <li key={c.id} className="ez-rise" style={{ "--i": i } as React.CSSProperties}>
                <Link
                  href={`${base}/classes/${c.id}`}
                  className="group flex h-full flex-col overflow-hidden rounded-ez-lg border border-border bg-surface shadow-ez-sm transition duration-300 ease-ez hover:-translate-y-0.5 hover:shadow-ez-lg"
                >
                  <div className="relative">
                    <ClassCover title={c.title} subject={c.subject} imageUrl={c.cover_image_url} label={c.exam ? t(`exam.${c.exam}`) : null} size="sm" />
                    <Badge tone={c.status} dot className="absolute top-3 right-3 shadow-ez-sm">
                      {t(`status.${c.status}`)}
                    </Badge>
                  </div>
                  <div className="flex flex-1 flex-col gap-2 p-5">
                    <p className="truncate text-xs font-bold tracking-[0.12em] text-brand-600 uppercase">{classMeta(t, c)}</p>
                    <p className="font-display text-lg leading-snug font-semibold">{c.title}</p>
                    <p className="mt-auto pt-2 text-sm">
                      <span className="font-semibold tabular-nums">{price.amount}</span>{" "}
                      {price.unit && <span className="text-muted">{price.unit}</span>}
                    </p>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}

      {res.ok && (cursor || res.data.next_cursor) && (
        <div className="flex justify-between">
          {cursor ? <Link href={href(status)} className={buttonStyles("secondary")}>{t("classes.firstPage")}</Link> : <span />}
          {res.data.next_cursor && (
            <Link href={href(status, res.data.next_cursor)} className={buttonStyles("secondary")}>
              {t("classes.loadMore")}
            </Link>
          )}
        </div>
      )}
    </>
  );
}
