import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { StudentHeader } from "@/components/student-header";
import { Badge, Card, ErrorText, buttonClass } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { errorText, t } from "@/lib/i18n";
import { getMe } from "@/lib/session";
import type { StudentLessonDetail } from "@/lib/types";

import { PdfResource, VideoResource } from "./player";

export default async function LessonPage({ params }: PageProps<"/lessons/[id]">) {
  const { id } = await params;
  if (!(await getMe())) redirect(`/login?next=/lessons/${id}`);
  const res = await api<StudentLessonDetail>(`/student/lessons/${id}`);
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    return <ErrorText>{errorText(t, res.error)}</ErrorText>;
  }
  const l = res.data;

  return (
    <>
      <StudentHeader />
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-5 px-4 py-6">
        <Link href={`/classes/${l.class_slug}`} className={`${buttonClass.link} text-sm`}>
          ← {l.class_title}
        </Link>
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold">{l.title}</h1>
            {l.is_free_preview && <Badge tone="upcoming">{t("class.freePreview")}</Badge>}
          </div>
          <p className="text-sm text-muted">
            {[t(`lessons.type.${l.lesson_type}`), l.scheduled_at && formatDateTime(l.scheduled_at),
              l.duration_minutes && `${l.duration_minutes} min`].filter(Boolean).join(" · ")}
          </p>
        </div>

        {!l.unlocked ? (
          <Card className="flex flex-col items-start gap-3">
            <h2 className="text-lg font-semibold">🔒 {t("lesson.lockedTitle")}</h2>
            <p className="text-muted">{t("lesson.lockedBody")}</p>
            <Link href={`/classes/${l.class_slug}`} className={buttonClass.primary}>{t("lesson.back")}</Link>
          </Card>
        ) : (
          <>
            {l.description && <p className="whitespace-pre-line">{l.description}</p>}
            {l.lesson_type === "live" && (
              <Card className="flex flex-col items-start gap-2">
                {l.zoom_join_url ? (
                  <a href={l.zoom_join_url} target="_blank" rel="noopener noreferrer" className={buttonClass.primary}>
                    {t("lesson.joinZoom")}
                  </a>
                ) : (
                  <p className="text-muted">{t("lesson.zoomLater")}</p>
                )}
              </Card>
            )}
            <Card className="flex flex-col gap-4">
              <h2 className="text-lg font-semibold">{t("lesson.materials")}</h2>
              {l.resources.length === 0 && <p className="text-sm text-muted">{t("lesson.noMaterials")}</p>}
              {l.resources.map((r) =>
                r.kind === "video" ? <VideoResource key={r.id} r={r} /> : <PdfResource key={r.id} r={r} />,
              )}
              {l.resources.some((r) => r.kind === "video") && (
                <p className="text-xs text-muted">{t("lesson.watermarkNote")}</p>
              )}
            </Card>
          </>
        )}
      </main>
    </>
  );
}
