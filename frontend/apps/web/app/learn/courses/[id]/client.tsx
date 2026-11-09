"use client";

import { CheckCircle2, Circle, Star } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { useT } from "@eduzone/lib/i18n/client";
import type { StudentResource } from "@eduzone/lib/types";
import { Button, ErrorText, toast } from "@eduzone/ui";

import { VideoResource } from "@/app/learn/lessons/[id]/player";

import { deleteReview, saveReview, setLectureComplete } from "../actions";

/** A lecture's video; when watching completes it, the curriculum's tick and the progress refresh. */
export function LectureVideo({ r }: { r: StudentResource }) {
  const router = useRouter();
  return <VideoResource r={r} onCompleted={() => router.refresh()} />;
}

/** "Mark as complete" for articles and PDFs (videos complete themselves), and its undo. */
export function CompleteButton({ courseId, lectureId, completed }: { courseId: string; lectureId: string; completed: boolean }) {
  const t = useT();
  const [pending, run] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const toggle = () => {
    setError(null);
    run(async () => {
      const res = await setLectureComplete(courseId, lectureId, !completed);
      if (!res.ok) setError(res.error);
      else if (!completed) toast(t("player.course.completed"));
    });
  };
  return (
    <div className="flex flex-col items-start gap-1">
      <Button variant={completed ? "secondary" : "primary"} loading={pending} onClick={toggle}
              icon={completed ? <CheckCircle2 className="size-4.5 text-success" /> : <Circle className="size-4.5" />}>
        {completed ? t("player.course.completed") : t("player.course.markComplete")}
      </Button>
      {completed && (
        <button type="button" onClick={toggle} disabled={pending} className="text-xs text-muted underline-offset-2 hover:underline">
          {t("player.course.markIncomplete")}
        </button>
      )}
      <ErrorText>{error}</ErrorText>
    </div>
  );
}

type Review = { rating: number; comment: string | null; status: string } | null;

/** "Rate this course": stars and an optional comment; once saved, the rating with Edit and Delete. Shown in the
 * player after a quarter of the course (or as soon as the student has rated). */
export function RatingCard({ courseId, review }: { courseId: string; review: Review }) {
  const t = useT();
  const [saved, setSaved] = useState(review !== null);
  const [editing, setEditing] = useState(review === null);
  const [rating, setRating] = useState(review?.rating ?? 0);
  const [hover, setHover] = useState(0);
  const [comment, setComment] = useState(review?.comment ?? "");
  const [pending, run] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const save = () => {
    if (!rating) { setError(t("rate.pick")); return; }
    setError(null);
    run(async () => {
      const res = await saveReview(courseId, rating, comment);
      if (!res.ok) setError(res.error);
      else { setSaved(true); setEditing(false); toast(t("rate.thanks")); }
    });
  };
  const remove = () => {
    if (!window.confirm(t("rate.confirmDelete"))) return;
    run(async () => {
      const res = await deleteReview(courseId);
      if (!res.ok) setError(res.error);
      else { setSaved(false); setRating(0); setComment(""); setEditing(true); }
    });
  };

  return (
    <section className="flex flex-col gap-3 rounded-ez-lg border border-gold/40 bg-gold/5 p-4">
      <div>
        <h2 className="font-semibold">{saved && !editing ? t("rate.yours") : t("rate.title")}</h2>
        {editing && <p className="text-sm text-muted">{t("rate.body")}</p>}
      </div>
      <div className="flex gap-1" role="radiogroup" aria-label={t("rate.title")} onMouseLeave={() => setHover(0)}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} type="button" role="radio" aria-checked={rating === n} aria-label={t("rate.star", { count: n })}
                  disabled={!editing || pending} onMouseEnter={() => editing && setHover(n)} onClick={() => setRating(n)}
                  className="rounded p-0.5 transition enabled:hover:scale-110 disabled:cursor-default">
            <Star className={(hover || rating) >= n ? "size-7 fill-gold text-gold" : "size-7 text-gold/45"} />
          </button>
        ))}
      </div>
      {editing ? (
        <>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-semibold">{t("rate.comment")}</span>
            <textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={3} maxLength={2000}
                      className="rounded-ez border border-border-strong bg-surface px-3 py-2 text-[0.9375rem] outline-none focus:border-brand focus:ring-4 focus:ring-brand/12" />
          </label>
          <ErrorText>{error}</ErrorText>
          <Button size="sm" className="self-start" loading={pending} onClick={save}>{saved ? t("rate.update") : t("rate.save")}</Button>
        </>
      ) : (
        <>
          {comment && <p className="text-sm whitespace-pre-line text-foreground/85">{comment}</p>}
          {review?.status === "hidden" && <p className="text-xs text-warning">{t("rate.hidden")}</p>}
          <div className="flex gap-4 text-sm">
            <button type="button" onClick={() => setEditing(true)} className="font-semibold text-brand hover:underline">{t("rate.edit")}</button>
            <button type="button" onClick={remove} disabled={pending} className="text-muted hover:text-danger hover:underline">{t("rate.delete")}</button>
          </div>
          <ErrorText>{error}</ErrorText>
        </>
      )}
    </section>
  );
}
