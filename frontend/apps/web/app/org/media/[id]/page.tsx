import Link from "next/link";
import { notFound } from "next/navigation";

import { ActionButton } from "@eduzone/ui/action-button";
import { Badge, Card, ErrorText, buttonClass } from "@eduzone/ui";
import { api } from "@/lib/api";
import { formatBytes, formatDateTime, formatDuration } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import { isPending, mediaTone } from "@/lib/media";
import type { Media, Preview } from "@eduzone/lib/types";

import { deleteMedia } from "../actions";
import { AutoRefresh } from "../uploaders";

export default async function MediaDetailPage({ params }: PageProps<"/org/media/[id]">) {
  const { id } = await params;
  const res = await api<Media>(`/org/media/${id}`); // also syncs a pending video's status
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    return <ErrorText>{errorText(t, res.error)}</ErrorText>;
  }
  const m = res.data;
  const preview = m.status === "ready" ? await api<Preview>(`/org/media/${id}/preview`) : null;

  return (
    <>
      <Link href="/org/media" className={`${buttonClass.link} text-sm`}>← {t("media.back")}</Link>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="truncate text-2xl font-semibold">{m.name}</h1>
            <Badge tone={mediaTone[m.status]}>{t(`media.status.${m.status}`)}</Badge>
          </div>
          <p className="text-sm text-muted">
            {[
              t(`media.kind.${m.kind}`),
              formatBytes(m.size_bytes),
              m.duration_seconds ? formatDuration(m.duration_seconds) : null,
              formatDateTime(m.created_at),
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <ActionButton
          action={deleteMedia.bind(null, m.id)}
          label={t("media.delete")}
          variant="danger"
          confirm={t("media.confirmDelete")}
        />
      </div>

      {isPending(m) && <p className="text-muted">{t("media.processingNote")}</p>}
      {preview && !preview.ok && <ErrorText>{errorText(t, preview.error)}</ErrorText>}
      {preview?.ok && m.kind === "video" && (
        <Card className="p-0 sm:p-0">
          {/* Staff preview of the signed embed. Students get the watermarked player (step 6). */}
          <div className="relative aspect-video overflow-hidden rounded-xl">
            <iframe
              src={preview.data.url}
              title={m.name}
              className="absolute inset-0 h-full w-full"
              allow="accelerometer; gyroscope; encrypted-media; picture-in-picture"
              allowFullScreen
              referrerPolicy="strict-origin"
            />
          </div>
        </Card>
      )}
      {preview?.ok && m.kind === "document" && (
        <a href={preview.data.url} target="_blank" rel="noopener noreferrer" className={`${buttonClass.primary} self-start`}>
          {t("media.open")}
        </a>
      )}
      <AutoRefresh active={isPending(m)} />
    </>
  );
}
