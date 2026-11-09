"use client";

import { CheckCircle2, Play } from "lucide-react";
import { useCallback, useEffect, useState, useTransition } from "react";

import { VideoPlayer } from "@/components/video-player";
import { ErrorText, buttonClass } from "@eduzone/ui";
import { formatDuration } from "@eduzone/lib/format";
import { useT } from "@eduzone/lib/i18n/client";
import type { OpenResource, StudentResource } from "@eduzone/lib/types";

import { openResource, saveProgress } from "@/app/learn/actions";

/** Student's name and phone drifting over Bunny's iframe (libraries without CDN keys). Our own player draws
 * its own watermark. Pointer events pass through to the player. */
function Watermark({ name, phone }: { name: string; phone: string | null }) {
  const [pos, setPos] = useState({ top: 12, left: 8 });
  useEffect(() => {
    const id = setInterval(() => setPos({ top: 5 + Math.random() * 80, left: 5 + Math.random() * 60 }), 20_000);
    return () => clearInterval(id);
  }, []);
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute z-10 rounded px-2 py-1 text-xs font-medium text-white/60 transition-all duration-1000 select-none sm:text-sm"
      style={{ top: `${pos.top}%`, left: `${pos.left}%`, textShadow: "0 1px 2px rgba(0,0,0,.6)" }}
    >
      {name}
      {phone ? ` · ${phone}` : ""}
    </div>
  );
}

export function VideoResource({ r, onCompleted }: {
  r: StudentResource;
  /** Called once when watching completes the video (a course lecture then completes too). */
  onCompleted?: () => void;
}) {
  const t = useT();
  const [opened, setOpened] = useState<OpenResource | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const [position, setPosition] = useState(r.position_seconds);
  const [completed, setCompleted] = useState(r.completed);
  const used = opened?.views_used ?? r.views_used;
  const allowed = opened?.views_allowed ?? r.views_allowed;

  // Each play session counts a view (the API refuses at the class's limit) and returns a short-lived URL.
  const play = useCallback(() => {
    setError(null);
    start(async () => {
      const res = await openResource(r.id);
      if (res.ok) setOpened(res.data);
      else setError(res.error);
    });
  }, [r.id]);

  const report = useCallback((positionSeconds: number, watchedSeconds: number) => {
    setPosition(Math.floor(positionSeconds));
    void saveProgress(r.id, positionSeconds, watchedSeconds).then((p) => {
      if (p?.completed && !completed) {
        setCompleted(true);
        onCompleted?.();
      }
    });
  }, [r.id, completed, onCompleted]);

  const expired = useCallback(() => setOpened(null), []);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 font-semibold">
          {completed && <CheckCircle2 className="size-4.5 text-success" aria-label={t("lesson.watched")} />}
          {r.title}
          {r.duration_seconds ? <span className="text-sm font-normal text-muted">· {formatDuration(r.duration_seconds)}</span> : null}
        </p>
        {allowed !== null && <span className="text-xs text-muted">{t("lesson.views", { used, allowed })}</span>}
      </div>

      {opened?.playback === "hls" ? (
        <VideoPlayer
          src={opened.url}
          title={r.title}
          resumeAt={opened.resume_at_seconds}
          watermark={opened.watermark}
          onProgress={report}
          onExpired={expired}
        />
      ) : opened ? (
        <div className="relative aspect-video overflow-hidden rounded-ez-lg bg-black">
          <iframe
            src={opened.url}
            title={r.title}
            className="absolute inset-0 h-full w-full"
            allow="accelerometer; gyroscope; encrypted-media; picture-in-picture; autoplay"
            allowFullScreen
            referrerPolicy="strict-origin"
          />
          <Watermark name={opened.watermark.name} phone={opened.watermark.phone} />
        </div>
      ) : (
        <button
          type="button"
          onClick={play}
          disabled={pending || !r.ready}
          className="group relative grid aspect-video w-full place-items-center overflow-hidden rounded-ez-lg bg-brand-900 text-on-brand disabled:opacity-70"
        >
          <span className="ez-grain absolute inset-0" aria-hidden />
          <span className="relative flex flex-col items-center gap-3">
            <span className="grid size-18 place-items-center rounded-full bg-gold text-brand-900 shadow-ez-lg transition group-hover:scale-105">
              <Play className="ml-1 size-8 fill-current" />
            </span>
            <span className="text-sm font-semibold">
              {!r.ready ? t("lesson.processing")
                : pending ? t("common.loading")
                : position > 0 && !completed ? t("lesson.continueAt", { time: formatDuration(position) })
                : t("lesson.play")}
            </span>
          </span>
          {r.duration_seconds && position > 0 ? (
            <span className="absolute inset-x-0 bottom-0 h-1 bg-white/15">
              <span className="block h-full bg-gold" style={{ width: `${Math.min(100, (position / r.duration_seconds) * 100)}%` }} />
            </span>
          ) : null}
        </button>
      )}
      {opened?.playback === "hls" && <p className="text-xs text-muted">{t("player.keys")}</p>}
      <ErrorText>{error}</ErrorText>
    </div>
  );
}

export function PdfResource({ r }: { r: StudentResource }) {
  const t = useT();
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function open() {
    // Open the tab now (popup blockers allow it inside the click), then point it at the signed URL.
    const tab = window.open("about:blank", "_blank");
    start(async () => {
      const res = await openResource(r.id);
      if (res.ok && tab) {
        tab.opener = null;
        tab.location.href = res.data.url;
      } else {
        tab?.close();
        setError(res.ok ? t("errors.generic") : res.error);
      }
    });
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="font-medium">{r.title}</p>
      <button className={`${buttonClass.secondary} min-h-9 px-3 text-sm`} onClick={open} disabled={pending}>
        {t("lesson.openPdf")}
      </button>
      <ErrorText>{error}</ErrorText>
    </div>
  );
}
