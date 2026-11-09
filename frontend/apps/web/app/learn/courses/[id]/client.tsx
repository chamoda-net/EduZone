"use client";

import { CheckCircle2, Circle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { useT } from "@eduzone/lib/i18n/client";
import type { StudentResource } from "@eduzone/lib/types";
import { Button, ErrorText, toast } from "@eduzone/ui";

import { VideoResource } from "@/app/learn/lessons/[id]/player";

import { setLectureComplete } from "../actions";

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
