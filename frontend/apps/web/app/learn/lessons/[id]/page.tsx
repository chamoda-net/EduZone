import { ArrowLeft, CalendarClock, ExternalLink, FileText, Lock, MonitorPlay, ShieldAlert, Video } from "lucide-react";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { SiteShell } from "@/components/shell";
import { api } from "@/lib/api";
import { getMe } from "@/lib/session";
import { formatDateTime } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";
import type { LessonType, StudentLessonDetail } from "@eduzone/lib/types";
import { Badge, Card, CardTitle, EmptyState, ErrorText, buttonStyles } from "@eduzone/ui";

import { PdfResource, VideoResource } from "./player";

const typeIcon: Record<LessonType, React.ReactNode> = {
  live: <Video />,
  recorded: <MonitorPlay />,
  document: <FileText />,
};

export default async function LessonPage({ params }: PageProps<"/learn/lessons/[id]">) {
  const { id } = await params;
  if (!(await getMe())) redirect(`/login?next=/learn/lessons/${id}`);
  const res = await api<StudentLessonDetail>(`/learn/lessons/${id}`);
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    return <SiteShell width="md"><ErrorText>{errorText(t, res.error)}</ErrorText></SiteShell>;
  }
  const l = res.data;

  return (
    <SiteShell width="md">
      <Link href={`/learn/classes/${l.class_id}`} className="inline-flex items-center gap-1.5 self-start text-sm font-semibold text-muted hover:text-foreground">
        <ArrowLeft className="size-4" />
        {l.class_title}
      </Link>

      <header className="ez-rise flex items-start gap-4">
        <span className="grid size-14 shrink-0 place-items-center rounded-ez-lg bg-brand-900 text-gold [&>svg]:size-6">
          {typeIcon[l.lesson_type]}
        </span>
        <div className="flex min-w-0 flex-col gap-1.5">
          <p className="text-xs font-bold tracking-[0.14em] text-brand-600 uppercase">{t(`lessons.type.${l.lesson_type}`)}</p>
          <h1 className="font-display text-3xl leading-tight font-semibold sm:text-4xl">{l.title}</h1>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
            {l.scheduled_at && (
              <span className="inline-flex items-center gap-1.5">
                <CalendarClock className="size-4" />
                {formatDateTime(l.scheduled_at)}
              </span>
            )}
            {l.duration_minutes && <span>{t("lesson.minutes", { count: l.duration_minutes })}</span>}
            {l.is_free_preview && <Badge tone="gold">{t("class.freePreview")}</Badge>}
          </div>
        </div>
      </header>

      {!l.unlocked ? (
        <EmptyState
          icon={<Lock />}
          title={t("lesson.lockedTitle")}
          body={t("lesson.lockedBody")}
          action={<Link href={`/learn/classes/${l.class_id}`} className={buttonStyles("primary")}>{t("lesson.back")}</Link>}
        />
      ) : (
        <>
          {l.lesson_type === "live" && (
            <div className="ez-grain ez-rise flex flex-col gap-4 overflow-hidden rounded-ez-lg bg-brand-900 p-6 text-on-brand sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-display text-xl font-semibold">{t("lesson.liveTitle")}</p>
                <p className="text-sm text-brand-100/80">{l.zoom_join_url ? t("lesson.liveBody") : t("lesson.zoomLater")}</p>
              </div>
              {l.zoom_join_url && (
                <a href={l.zoom_join_url} target="_blank" rel="noopener noreferrer" className={buttonStyles("gold", "lg")}>
                  {t("lesson.joinZoom")}
                  <ExternalLink className="size-4" />
                </a>
              )}
            </div>
          )}
          {l.description && <p className="text-[1.0625rem] leading-relaxed whitespace-pre-line text-foreground/85">{l.description}</p>}
          <Card className="flex flex-col gap-5">
            <CardTitle>{t("lesson.materials")}</CardTitle>
            {l.resources.length === 0 && <p className="text-sm text-muted">{t("lesson.noMaterials")}</p>}
            {l.resources.map((r) => (r.kind === "video" ? <VideoResource key={r.id} r={r} /> : <PdfResource key={r.id} r={r} />))}
            {l.resources.some((r) => r.kind === "video") && (
              <p className="flex items-start gap-2 rounded-ez bg-gold-100 px-3 py-2.5 text-xs text-gold-strong">
                <ShieldAlert className="mt-px size-4 shrink-0" />
                {t("lesson.watermarkNote")}
              </p>
            )}
          </Card>
        </>
      )}
    </SiteShell>
  );
}
