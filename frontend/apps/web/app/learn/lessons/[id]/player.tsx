"use client";

import { useEffect, useState, useTransition } from "react";

import { ErrorText, buttonClass } from "@eduzone/ui";
import { formatDuration } from "@eduzone/lib/format";
import { useT } from "@eduzone/lib/i18n/client";
import type { OpenResource, StudentResource } from "@eduzone/lib/types";

import { openResource } from "@/app/learn/actions";

/** Student's name and phone drifting over the video, so a screen recording identifies who
 * shared it (CLAUDE.md section 10). Pointer events pass through to the player. */
function Watermark({ name, phone }: { name: string; phone: string | null }) {
  const [pos, setPos] = useState({ top: 12, left: 8 });
  useEffect(() => {
    const id = setInterval(() => setPos({ top: 5 + Math.random() * 80, left: 5 + Math.random() * 60 }), 7000);
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

export function VideoResource({ r }: { r: StudentResource }) {
  const t = useT();
  const [opened, setOpened] = useState<OpenResource | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const used = opened?.views_used ?? r.views_used;
  const allowed = opened?.views_allowed ?? r.views_allowed;

  function play() {
    start(async () => {
      const res = await openResource(r.id);
      if (res.ok) setOpened(res.data);
      else setError(res.error);
    });
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-medium">
          {r.title}
          {r.duration_seconds ? <span className="text-sm font-normal text-muted"> · {formatDuration(r.duration_seconds)}</span> : null}
        </p>
        {allowed !== null && <span className="text-xs text-muted">{t("lesson.views", { used, allowed })}</span>}
      </div>
      {opened ? (
        <div className="relative aspect-video overflow-hidden rounded-xl bg-black">
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
        <button className={`${buttonClass.primary} self-start`} onClick={play} disabled={pending || !r.ready}>
          {r.ready ? (pending ? t("common.loading") : `▶ ${t("lesson.play")}`) : t("lesson.processing")}
        </button>
      )}
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
