"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { api } from "@/lib/api";
import { errorText, t } from "@eduzone/lib/i18n";
import type { LessonResource, VideoUpload } from "@eduzone/lib/types";

import type { FormState } from "../classes/actions";

export type StartVideoResult = { ok: true; upload: VideoUpload } | { ok: false; error: string };

/** Creates the video at Bunny and returns a short-lived TUS signature; the browser then
 * uploads the file straight to Bunny (it never passes through our servers). */
export async function startVideoUpload(file: { name: string; size: number; type: string }): Promise<StartVideoResult> {
  const res = await api<VideoUpload>("/org/media/videos", {
    method: "POST",
    body: { filename: file.name.slice(0, 200), size_bytes: file.size, mime_type: file.type || null },
  });
  if (!res.ok) return { ok: false, error: errorText(t, res.error) };
  revalidatePath("/org/media");
  return { ok: true, upload: res.data };
}

export async function deleteMedia(mediaId: string): Promise<FormState> {
  const res = await api(`/org/media/${mediaId}`, { method: "DELETE" });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath("/org/media");
  redirect("/org/media");
}

export async function attachFile(classId: string, lessonId: string, _: FormState, fd: FormData): Promise<FormState> {
  const title = String(fd.get("title") ?? "").trim();
  const res = await api<LessonResource>(`/org/lessons/${lessonId}/resources`, {
    method: "POST",
    body: {
      media_asset_id: String(fd.get("media_asset_id") ?? ""),
      title: title || null,
      is_downloadable: fd.get("is_downloadable") === "on",
    },
  });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath(`/org/classes/${classId}`);
  return { ok: true, at: Date.now() };
}

export async function removeFile(classId: string, resourceId: string): Promise<FormState> {
  const res = await api(`/org/lesson-resources/${resourceId}`, { method: "DELETE" });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath(`/org/classes/${classId}`);
  return { ok: true };
}
