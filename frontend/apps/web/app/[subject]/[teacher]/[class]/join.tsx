"use client";

import { ArrowRight, Loader2, Play, PlayCircle } from "lucide-react";
import { useState, useTransition } from "react";

import { VideoPlayer } from "@/components/video-player";
import { useT } from "@eduzone/lib/i18n/client";
import { Button, Dialog, ErrorText, cx } from "@eduzone/ui";

import { joinNow, loadLessonPreview } from "./actions";

/** "Join December · Rs. 2,500": adds the month to the cart and opens it (guests sign in or register there). */
export function JoinNowButton({ classId, monthId, label }: { classId: string; monthId: string | null; label: string }) {
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="flex w-full flex-col gap-2">
      <Button type="button" size="lg" className="w-full" loading={pending}
              onClick={() => start(async () => {
                setError(null);
                const res = await joinNow(classId, monthId);
                if (res && !res.ok) setError(res.error);
              })}>
        {label}
        <ArrowRight className="size-4.5" />
      </Button>
      {error && <ErrorText>{error}</ErrorText>}
    </div>
  );
}

type Playing = { url: string; playback: string; title: string; key: number };

/** A free-preview lesson with a video, played in a dialog for anyone (no sign-in, no watermark, no view counted). */
export function LessonPreview({ lessonId, title, trigger, className }: {
  lessonId: string;
  title: string;
  trigger: React.ReactNode;
  className?: string;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [playing, setPlaying] = useState<Playing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, run] = useTransition();

  const play = () => {
    setError(null);
    run(async () => {
      const res = await loadLessonPreview(lessonId);
      if (res.ok) setPlaying({ url: res.data.url, playback: res.data.playback, title: res.data.title, key: Date.now() });
      else setError(res.error);
    });
  };

  return (
    <Dialog
      title={title}
      description={t("market.class.previewing")}
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) play();
        else setPlaying(null);
      }}
      trigger={<button type="button" className={cx("inline-flex", className)} aria-label={t("market.class.previewLesson", { title })}>{trigger}</button>}
    >
      <div className="flex flex-col gap-4">
        <div className="relative aspect-video overflow-hidden rounded-ez bg-brand-950">
          {playing?.playback === "hls" && (
            <VideoPlayer key={playing.key} src={playing.url} title={playing.title} resumeAt={0}
                         onProgress={() => {}} onExpired={() => setPlaying(null)} />
          )}
          {playing?.playback === "embed" && (
            <iframe key={playing.key} src={playing.url} title={playing.title} className="absolute inset-0 h-full w-full"
                    allow="encrypted-media; autoplay; fullscreen" allowFullScreen referrerPolicy="strict-origin" />
          )}
          {(!playing || pending) && (
            <div className="absolute inset-0 grid place-items-center text-on-brand">
              {pending ? <Loader2 className="size-8 animate-spin" aria-label={t("common.loading")} /> : <Play className="size-10" />}
            </div>
          )}
        </div>
        <ErrorText>{error}</ErrorText>
        {!error && (
          <p className="flex items-center gap-2 text-sm text-muted">
            <PlayCircle className="size-4 shrink-0 text-brand-600" />
            {t("market.class.previewHint")}
          </p>
        )}
      </div>
    </Dialog>
  );
}
