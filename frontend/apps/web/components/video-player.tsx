"use client";

import type HlsType from "hls.js";
import { Gauge, Loader2, Maximize, Minimize, Pause, Play, RotateCcw, RotateCw, Settings2, Volume2, VolumeX } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { formatDuration } from "@eduzone/lib/format";
import { useT } from "@eduzone/lib/i18n/client";
import { cx } from "@eduzone/ui";

const SPEEDS = [0.75, 1, 1.25, 1.5, 1.75, 2];
const REPORT_EVERY_MS = 15_000;
const WATERMARK_EVERY_MS = 20_000;
const HIDE_CONTROLS_MS = 2500;

type Level = { index: number; height: number };

/** Student's name and phone drifting over the video, inside the player so it stays in full screen and shows in
 * any screen recording (CLAUDE.md section 10). Pointer events pass through. */
function Watermark({ name, phone }: { name: string; phone: string | null }) {
  const [pos, setPos] = useState({ top: 12, left: 8 });
  useEffect(() => {
    const id = setInterval(() => setPos({ top: 6 + Math.random() * 70, left: 4 + Math.random() * 56 }), WATERMARK_EVERY_MS);
    return () => clearInterval(id);
  }, []);
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute z-10 rounded px-2 py-1 text-xs font-semibold text-white/55 transition-all duration-[1500ms] select-none sm:text-sm"
      style={{ top: `${pos.top}%`, left: `${pos.left}%`, textShadow: "0 1px 3px rgba(0,0,0,.7)" }}
    >
      {name}
      {phone ? ` · ${phone.slice(0, -4).replace(/\d/g, "•")}${phone.slice(-4)}` : ""}
    </div>
  );
}

/** Our own HLS player (hls.js; Safari plays HLS natively). Resumes at `resumeAt`, reports position and time
 * actually watched every 15 s and on pause or leaving, and keeps the watermark on top, in full screen too. */
export function VideoPlayer({ src, title, resumeAt, watermark, onProgress, onExpired }: {
  src: string;
  title: string;
  resumeAt: number;
  /** The student's name and phone over the video; none for public previews. */
  watermark?: { name: string; phone: string | null };
  onProgress: (positionSeconds: number, watchedSeconds: number) => void;
  /** The signed URL stopped working (expired): ask for a new one. */
  onExpired: () => void;
}) {
  const t = useT();
  const box = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const hls = useRef<HlsType | null>(null);
  const watched = useRef(0);
  const lastTime = useRef(0);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [playing, setPlaying] = useState(false);
  const [waiting, setWaiting] = useState(true);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [buffered, setBuffered] = useState(0);
  const [muted, setMuted] = useState(false);
  const [rate, setRate] = useState(1);
  const [levels, setLevels] = useState<Level[]>([]);
  const [level, setLevel] = useState(-1);
  const [menu, setMenu] = useState<null | "speed" | "quality">(null);
  const [full, setFull] = useState(false);
  const [shown, setShown] = useState(true);
  const [resumed, setResumed] = useState<number | null>(null);
  const [error, setError] = useState(false);

  // --- reporting --------------------------------------------------------------------------
  const flush = useCallback(() => {
    const v = video.current;
    if (!v || (watched.current < 1 && Math.abs(v.currentTime - lastTime.current) < 1)) return;
    onProgress(v.currentTime, watched.current);
    watched.current = 0;
  }, [onProgress]);

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(flush, REPORT_EVERY_MS);
    return () => clearInterval(id);
  }, [playing, flush]);

  useEffect(() => {
    const away = () => document.visibilityState === "hidden" && flush();
    document.addEventListener("visibilitychange", away);
    return () => {
      document.removeEventListener("visibilitychange", away);
      flush();
    };
  }, [flush]);

  // --- source -----------------------------------------------------------------------------
  useEffect(() => {
    const v = video.current;
    if (!v) return;
    let cancelled = false;
    setError(false);
    setWaiting(true);
    if (v.canPlayType("application/vnd.apple.mpegurl")) {
      v.src = src; // Safari and iOS play HLS themselves
    } else {
      void import("hls.js").then(({ default: Hls }) => {
        if (cancelled) return;
        if (!Hls.isSupported()) {
          setError(true);
          return;
        }
        const h = new Hls({ capLevelToPlayerSize: true, maxBufferLength: 30 });
        hls.current = h;
        h.on(Hls.Events.MANIFEST_PARSED, () => {
          const seen = new Set<number>();
          setLevels(h.levels
            .map((l, index) => ({ index, height: l.height }))
            .filter((l) => l.height && !seen.has(l.height) && seen.add(l.height))
            .sort((a, b) => b.height - a.height));
        });
        h.on(Hls.Events.ERROR, (_e, data) => {
          if (!data.fatal) return;
          const status = data.response?.code;
          if (status === 401 || status === 403) {
            onExpired();
          } else if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
            setError(true);
          } else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
            h.recoverMediaError();
          } else {
            setError(true);
          }
        });
        h.loadSource(src);
        h.attachMedia(v);
      });
    }
    return () => {
      cancelled = true;
      hls.current?.destroy();
      hls.current = null;
    };
  }, [src, onExpired]);

  // --- controls ---------------------------------------------------------------------------
  const poke = useCallback(() => {
    setShown(true);
    if (hideTimer.current) clearTimeout(hideTimer.current);
    hideTimer.current = setTimeout(() => {
      if (!video.current?.paused) {
        setShown(false);
        setMenu(null);
      }
    }, HIDE_CONTROLS_MS);
  }, []);

  const toggle = useCallback(() => {
    const v = video.current;
    if (!v) return;
    if (v.paused) void v.play().catch(() => {});
    else v.pause();
    poke();
  }, [poke]);

  const skip = useCallback((by: number) => {
    const v = video.current;
    if (!v) return;
    v.currentTime = Math.min(Math.max(0, v.currentTime + by), v.duration || v.currentTime + by);
    lastTime.current = v.currentTime;
    poke();
  }, [poke]);

  const toggleFull = useCallback(() => {
    const el = box.current;
    const v = video.current as (HTMLVideoElement & { webkitEnterFullscreen?: () => void }) | null;
    if (document.fullscreenElement) void document.exitFullscreen();
    else if (el?.requestFullscreen) void el.requestFullscreen().catch(() => v?.webkitEnterFullscreen?.());
    else v?.webkitEnterFullscreen?.(); // iPhone: only the video itself can go full screen
  }, []);

  useEffect(() => {
    const on = () => setFull(document.fullscreenElement === box.current);
    document.addEventListener("fullscreenchange", on);
    return () => document.removeEventListener("fullscreenchange", on);
  }, []);

  function onKey(e: React.KeyboardEvent) {
    const k = e.key.toLowerCase();
    if (k === " " || k === "k") toggle();
    else if (k === "j" || k === "arrowleft") skip(-10);
    else if (k === "l" || k === "arrowright") skip(10);
    else if (k === "f") toggleFull();
    else if (k === "m" && video.current) video.current.muted = !video.current.muted;
    else return;
    e.preventDefault();
  }

  function chooseLevel(index: number) {
    if (hls.current) hls.current.currentLevel = index;
    setLevel(index);
    setMenu(null);
  }

  function chooseRate(r: number) {
    if (video.current) video.current.playbackRate = r;
    setRate(r);
    setMenu(null);
  }

  const pct = duration ? (time / duration) * 100 : 0;
  const bufPct = duration ? (buffered / duration) * 100 : 0;
  const visible = shown || !playing || menu !== null;

  return (
    <div
      ref={box}
      tabIndex={0}
      onKeyDown={onKey}
      onMouseMove={poke}
      onTouchStart={poke}
      onContextMenu={(e) => e.preventDefault()}
      aria-label={title}
      className={cx(
        "group relative aspect-video w-full overflow-hidden rounded-ez-lg bg-black text-white outline-none select-none focus-visible:ring-2 focus-visible:ring-gold",
        full && "rounded-none",
        !visible && "cursor-none",
      )}
    >
      <video
        ref={video}
        className="absolute inset-0 h-full w-full"
        playsInline
        preload="metadata"
        controlsList="nodownload noplaybackrate"
        disablePictureInPicture
        onClick={toggle}
        onPlay={() => setPlaying(true)}
        onPause={() => {
          setPlaying(false);
          flush();
        }}
        onEnded={() => {
          setPlaying(false);
          flush();
        }}
        onWaiting={() => setWaiting(true)}
        onPlaying={() => setWaiting(false)}
        onCanPlay={() => setWaiting(false)}
        onVolumeChange={(e) => setMuted(e.currentTarget.muted)}
        onLoadedMetadata={(e) => {
          const v = e.currentTarget;
          setDuration(v.duration);
          if (resumeAt > 0 && resumeAt < v.duration - 15) {
            v.currentTime = resumeAt;
            setResumed(resumeAt);
            setTimeout(() => setResumed(null), 6000);
          }
          lastTime.current = v.currentTime;
          // They pressed Play to get here: start (browsers may refuse; the big play button stays then).
          void v.play().catch(() => setWaiting(false));
        }}
        onTimeUpdate={(e) => {
          const v = e.currentTarget;
          const delta = v.currentTime - lastTime.current;
          // Only real playback counts as watched, not seeking.
          if (!v.paused && delta > 0 && delta < 2) watched.current += delta;
          lastTime.current = v.currentTime;
          setTime(v.currentTime);
          if (v.buffered.length) setBuffered(v.buffered.end(v.buffered.length - 1));
        }}
      />

      {watermark && <Watermark name={watermark.name} phone={watermark.phone} />}

      {waiting && !error && (
        <div className="pointer-events-none absolute inset-0 z-10 grid place-items-center">
          <Loader2 className="size-10 animate-spin text-white/80" />
        </div>
      )}

      {!playing && !waiting && !error && (
        <button
          type="button"
          onClick={toggle}
          aria-label={t("player.play")}
          className="absolute inset-0 z-10 m-auto grid size-18 place-items-center rounded-full bg-gold text-brand-900 shadow-ez-lg transition hover:scale-105"
        >
          <Play className="ml-1 size-8 fill-current" />
        </button>
      )}

      {error && (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 bg-black/80 p-6 text-center">
          <p className="max-w-sm text-sm">{t("player.error")}</p>
          <button type="button" onClick={onExpired} className="rounded-full bg-white px-4 py-2 text-sm font-semibold text-black">
            {t("player.retry")}
          </button>
        </div>
      )}

      {resumed !== null && (
        <div className="absolute top-3 left-3 z-20 flex items-center gap-2 rounded-full bg-black/70 py-1 pr-1 pl-3 text-xs font-medium backdrop-blur">
          {t("player.resumed", { time: formatDuration(Math.floor(resumed)) })}
          <button
            type="button"
            onClick={() => {
              if (video.current) video.current.currentTime = 0;
              lastTime.current = 0;
              setResumed(null);
            }}
            className="rounded-full bg-white/15 px-2.5 py-1 font-semibold hover:bg-white/25"
          >
            {t("player.startOver")}
          </button>
        </div>
      )}

      <div
        className={cx(
          "absolute inset-x-0 bottom-0 z-20 flex flex-col gap-1 bg-gradient-to-t from-black/85 via-black/50 to-transparent px-3 pt-10 pb-2 transition-opacity duration-300 sm:px-4",
          visible ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      >
        <div className="relative h-4">
          <div className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 overflow-hidden rounded-full bg-white/25">
            <div className="absolute inset-y-0 left-0 bg-white/35" style={{ width: `${bufPct}%` }} />
            <div className="absolute inset-y-0 left-0 bg-gold" style={{ width: `${pct}%` }} />
          </div>
          <input
            type="range"
            aria-label={t("player.seek")}
            min={0}
            max={duration || 0}
            step={1}
            value={time}
            onChange={(e) => {
              const v = video.current;
              if (!v) return;
              v.currentTime = Number(e.target.value);
              lastTime.current = v.currentTime;
              setTime(v.currentTime);
              poke();
            }}
            className="ez-seek absolute inset-0 h-4 w-full cursor-pointer appearance-none"
            style={{ background: "transparent", border: 0, boxShadow: "none" }}
          />
        </div>

        <div className="flex items-center gap-1 sm:gap-2">
          <IconButton label={playing ? t("player.pause") : t("player.play")} onClick={toggle}>
            {playing ? <Pause className="size-5 fill-current" /> : <Play className="size-5 fill-current" />}
          </IconButton>
          <IconButton label={t("player.back10")} onClick={() => skip(-10)}><RotateCcw className="size-5" /></IconButton>
          <IconButton label={t("player.forward10")} onClick={() => skip(10)}><RotateCw className="size-5" /></IconButton>
          <IconButton
            label={muted ? t("player.unmute") : t("player.mute")}
            onClick={() => video.current && (video.current.muted = !video.current.muted)}
          >
            {muted ? <VolumeX className="size-5" /> : <Volume2 className="size-5" />}
          </IconButton>
          <span className="ml-1 text-xs font-medium whitespace-nowrap tabular-nums sm:text-sm">
            {formatDuration(Math.floor(time))} / {formatDuration(Math.floor(duration || 0))}
          </span>

          <div className="relative ml-auto flex items-center gap-1">
            <IconButton label={t("player.speed")} onClick={() => setMenu(menu === "speed" ? null : "speed")}>
              <span className="flex items-center gap-1 text-xs font-semibold"><Gauge className="size-5" />{rate}×</span>
            </IconButton>
            {levels.length > 1 && (
              <IconButton label={t("player.quality")} onClick={() => setMenu(menu === "quality" ? null : "quality")}>
                <Settings2 className="size-5" />
              </IconButton>
            )}
            <IconButton label={full ? t("player.exitFullscreen") : t("player.fullscreen")} onClick={toggleFull}>
              {full ? <Minimize className="size-5" /> : <Maximize className="size-5" />}
            </IconButton>

            {menu && (
              <div role="menu" className="absolute right-0 bottom-12 min-w-36 overflow-hidden rounded-ez bg-black/90 py-1 text-sm shadow-ez-lg backdrop-blur">
                <p className="px-3 py-1.5 text-xs font-semibold tracking-wide text-white/60 uppercase">
                  {menu === "speed" ? t("player.speed") : t("player.quality")}
                </p>
                {menu === "speed" && SPEEDS.map((s) => (
                  <MenuItem key={s} active={s === rate} onClick={() => chooseRate(s)}>{s}×</MenuItem>
                ))}
                {menu === "quality" && (
                  <>
                    <MenuItem active={level === -1} onClick={() => chooseLevel(-1)}>{t("player.auto")}</MenuItem>
                    {levels.map((l) => (
                      <MenuItem key={l.index} active={level === l.index} onClick={() => chooseLevel(l.index)}>{l.height}p</MenuItem>
                    ))}
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function IconButton({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="grid min-h-10 min-w-10 place-items-center rounded-full px-1.5 text-white/90 transition hover:bg-white/15 hover:text-white"
    >
      {children}
    </button>
  );
}

function MenuItem({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      role="menuitemradio"
      aria-checked={active}
      onClick={onClick}
      className={cx("block w-full px-3 py-2 text-left hover:bg-white/10", active && "font-semibold text-gold")}
    >
      {children}
    </button>
  );
}
