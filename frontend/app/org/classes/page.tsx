import Link from "next/link";

import { Badge, ErrorText, buttonClass } from "@/components/ui";
import { api } from "@/lib/api";
import { classMeta, priceLabel } from "@/lib/catalog";
import { errorText, t } from "@/lib/i18n";
import type { ClassPage, ClassStatus } from "@/lib/types";

const FILTERS: (ClassStatus | null)[] = [null, "draft", "published", "archived"];

export default async function ClassesPage({ searchParams }: PageProps<"/org/classes">) {
  const sp = await searchParams;
  const status = FILTERS.includes(sp.status as ClassStatus) ? (sp.status as ClassStatus) : null;
  const cursor = typeof sp.cursor === "string" ? sp.cursor : null;

  const query = new URLSearchParams({ limit: "20" });
  if (status) query.set("status", status);
  if (cursor) query.set("cursor", cursor);
  const res = await api<ClassPage>(`/org/classes?${query}`);

  const href = (s: ClassStatus | null, c?: string) => {
    const q = new URLSearchParams();
    if (s) q.set("status", s);
    if (c) q.set("cursor", c);
    return q.size ? `/org/classes?${q}` : "/org/classes";
  };

  return (
    <>
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">{t("classes.title")}</h1>
        <Link href="/org/classes/new" className={buttonClass.primary}>
          {t("classes.new")}
        </Link>
      </div>

      <div className="flex gap-2 overflow-x-auto">
        {FILTERS.map((f) => (
          <Link
            key={f ?? "all"}
            href={href(f)}
            className={`rounded-full border px-3 py-1.5 text-sm whitespace-nowrap ${
              f === status ? "border-brand bg-brand text-white" : "border-border bg-surface"
            }`}
          >
            {f ? t(`status.${f}`) : t("classes.filter.all")}
          </Link>
        ))}
      </div>

      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && res.data.items.length === 0 && <p className="text-muted">{t("classes.empty")}</p>}
      {res.ok && res.data.items.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
          {res.data.items.map((c) => (
            <li key={c.id}>
              <Link href={`/org/classes/${c.id}`} className="flex flex-col gap-1 p-4 hover:bg-background sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="truncate font-medium">{c.title}</p>
                  <p className="truncate text-sm text-muted">{classMeta(t, c)}</p>
                </div>
                <div className="flex items-center gap-3 text-sm">
                  <span>{priceLabel(t, c)}</span>
                  <Badge tone={c.status}>{t(`status.${c.status}`)}</Badge>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {res.ok && (cursor || res.data.next_cursor) && (
        <div className="flex justify-between">
          {cursor ? <Link href={href(status)} className={buttonClass.link}>{t("classes.firstPage")}</Link> : <span />}
          {res.data.next_cursor && (
            <Link href={href(status, res.data.next_cursor)} className={buttonClass.link}>
              {t("classes.loadMore")}
            </Link>
          )}
        </div>
      )}
    </>
  );
}
