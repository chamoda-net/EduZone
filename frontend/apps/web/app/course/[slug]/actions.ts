"use server";

import type { Schema } from "@eduzone/api-client";
import { api } from "@/lib/api";
import { errorText, t } from "@eduzone/lib/i18n";

type Preview = Schema<"CoursePreviewOut">;

/** A short-lived stream of the course's promo video or of a free-preview lecture (anyone may watch). */
export async function loadPreview(slug: string, lectureId: string | null): Promise<{ ok: true; data: Preview } | { ok: false; error: string }> {
  const res = await api<Preview>(`/market/course/${encodeURIComponent(slug)}/preview`, {
    method: "POST", body: { lecture_id: lectureId }, token: null,
  });
  return res.ok ? { ok: true, data: res.data } : { ok: false, error: errorText(t, res.error) };
}
