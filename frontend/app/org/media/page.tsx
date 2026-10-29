import Link from "next/link";

import { Badge, Card, ErrorText, buttonClass } from "@/components/ui";
import { api } from "@/lib/api";
import { formatBytes, formatDuration } from "@/lib/format";
import { errorText, t } from "@/lib/i18n";
import { isPending, mediaTone } from "@/lib/media";
import type { Media, MediaKind, MediaPage } from "@/lib/types";

import { AutoRefresh, PdfUploader, VideoUploader } from "./uploaders";

const FILTERS: (MediaKind | null)[] = [null, "video", "document"];

/** Fetching a video that is still at Bunny's end makes the API sync its status. */
async function syncIfPending(m: Media): Promise<Media> {
  if (m.kind !== "video" || !isPending(m)) return m;
  const fresh = await api<Media>(`/org/media/${m.id}`);
  return fresh.ok ? fresh.data : m;
}

export default async function MediaPageView({ searchParams }: PageProps<"/org/media">) {
  const sp = await searchParams;
  const kind = FILTERS.includes(sp.kind as MediaKind) ? (sp.kind as MediaKind) : null;
  const cursor = typeof sp.cursor === "string" ? sp.cursor : null;
  const query = new URLSearchParams({ limit: "30" });
  if (kind) query.set("kind", kind);
  if (cursor) query.set("cursor", cursor);
  const res = await api<MediaPage>(`/org/media?${query}`);

  const items: Media[] = res.ok ? await Promise.all(res.data.items.map(syncIfPending)) : [];

  const href = (k: MediaKind | null, c?: string) => {
    const q = new URLSearchParams();
    if (k) q.set("kind", k);
    if (c) q.set("cursor", c);
    return q.size ? `/org/media?${q}` : "/org/media";
  };

  return (
    <>
      <div>
        <h1 className="text-2xl font-semibold">{t("media.title")}</h1>
        <p className="text-sm text-muted">{t("media.subtitle")}</p>
      </div>

      <Card className="grid gap-6 sm:grid-cols-2">
        <VideoUploader />
        <PdfUploader />
      </Card>

      <div className="flex gap-2 overflow-x-auto">
        {FILTERS.map((f) => (
          <Link
            key={f ?? "all"}
            href={href(f)}
            className={`rounded-full border px-3 py-1.5 text-sm whitespace-nowrap ${
              f === kind ? "border-brand bg-brand text-white" : "border-border bg-surface"
            }`}
          >
            {f ? t(`media.filter.${f}`) : t("classes.filter.all")}
          </Link>
        ))}
      </div>

      {!res.ok && <ErrorText>{errorText(t, res.error)}</ErrorText>}
      {res.ok && items.length === 0 && <p className="text-muted">{t("media.empty")}</p>}
      {items.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
          {items.map((m) => (
            <li key={m.id}>
              <Link href={`/org/media/${m.id}`} className="flex flex-col gap-1 p-4 hover:bg-background sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="truncate font-medium">{m.name}</p>
                  <p className="text-sm text-muted">
                    {[t(`media.kind.${m.kind}`), formatBytes(m.size_bytes), m.duration_seconds ? formatDuration(m.duration_seconds) : null]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                </div>
                <Badge tone={mediaTone[m.status]}>{t(`media.status.${m.status}`)}</Badge>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {res.ok && res.data.next_cursor && (
        <Link href={href(kind, res.data.next_cursor)} className={`${buttonClass.link} self-end`}>
          {t("classes.loadMore")}
        </Link>
      )}
      <AutoRefresh active={items.some(isPending)} />
    </>
  );
}
