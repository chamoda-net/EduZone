"use client";

import { Loader2, Play, PlayCircle } from "lucide-react";
import { useState, useTransition } from "react";

import { VideoPlayer } from "@/components/video-player";
import { useT } from "@eduzone/lib/i18n/client";
import { Dialog, ErrorText, cx } from "@eduzone/ui";

import { loadPreview } from "./actions";

type Item = { id: string | null; title: string; seconds: number };
type Playing = { url: string; playback: string; title: string; key: number };

function minutes(seconds: number): string {
  const m = Math.floor(seconds / 60);
  return `${m}:${String(Math.round(seconds % 60)).padStart(2, "0")}`;
}

/** The course's previews in one dialog: the promo video first, then each free-preview lecture. Opened from the
 * hero ("Preview this course") or from a lecture's "Preview" link in the curriculum. */
export function PreviewDialog({ slug, items, trigger, start }: {
  slug: string;
  items: Item[];
  trigger: React.ReactNode;
  start?: string | null;          // the item to play first (a lecture id; null = the promo)
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [playing, setPlaying] = useState<Playing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, run] = useTransition();

  const play = (item: Item) => {
    setError(null);
    run(async () => {
      const res = await loadPreview(slug, item.id);
      if (res.ok) setPlaying({ url: res.data.url, playback: res.data.playback, title: res.data.title, key: Date.now() });
      else setError(res.error);
    });
  };

  return (
    <Dialog
      title={t("market.course.previewing")}
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) {
          const first = items.find((i) => i.id === (start ?? items[0]?.id)) ?? items[0];
          if (first) play(first);
        } else {
          setPlaying(null);
        }
      }}
      trigger={trigger}
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
        {items.length > 1 && (
          <ul className="flex flex-col divide-y divide-border rounded-ez border border-border">
            {items.map((item) => {
              const current = playing?.title === item.title;
              return (
                <li key={item.id ?? "promo"}>
                  <button type="button" onClick={() => play(item)}
                          className={cx("flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm transition hover:bg-sunken",
                                        current && "bg-brand-50 font-semibold")}>
                    <PlayCircle className={cx("size-4.5 shrink-0", current ? "text-brand" : "text-muted")} aria-hidden />
                    <span className="min-w-0 flex-1 truncate">{item.title}</span>
                    {item.seconds > 0 && <span className="text-xs text-muted tabular-nums">{minutes(item.seconds)}</span>}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </Dialog>
  );
}
