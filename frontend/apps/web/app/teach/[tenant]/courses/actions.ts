"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import type { Schema } from "@eduzone/api-client";
import { api } from "@/lib/api";
import { teachHref } from "@/lib/workspace";
import { rupeesToCents } from "@eduzone/lib/format";
import { errorText, t } from "@eduzone/lib/i18n";

// The API checks permissions and every course rule; these actions only shape requests and errors.

export type FormState = { error?: string; ok?: boolean; at?: number };
type CourseDetail = Schema<"CourseDetail">;

const text = (fd: FormData, name: string) => String(fd.get(name) ?? "").trim();
const textOrNull = (fd: FormData, name: string) => text(fd, name) || null;
const list = (fd: FormData, name: string) => fd.getAll(name).map((v) => String(v).trim()).filter(Boolean);

async function refresh(courseId?: string) {
  revalidatePath(await teachHref("/courses"));
  if (courseId) revalidatePath(await teachHref(`/courses/${courseId}`));
}

async function patch(courseId: string, body: Record<string, unknown>): Promise<FormState> {
  const res = await api<CourseDetail>(`~/courses/${courseId}`, { method: "PATCH", body });
  if (!res.ok) return { error: errorText(t, res.error) };
  await refresh(courseId);
  return { ok: true, at: Date.now() };
}

/** A one-click call whose result is the course (curriculum edits, status changes). */
async function call(courseId: string, path: string, method: "POST" | "PATCH" | "DELETE", body?: unknown): Promise<FormState> {
  const res = await api<CourseDetail>(path, { method, body });
  if (!res.ok) return { error: errorText(t, res.error) };
  await refresh(courseId);
  return { ok: true, at: Date.now() };
}

// --- course -------------------------------------------------------------------------------

export async function createCourse(_: FormState, fd: FormData): Promise<FormState> {
  const category = text(fd, "category_id");
  const res = await api<CourseDetail>("~/courses", {
    method: "POST", body: { title: text(fd, "title"), category_id: category ? Number(category) : null },
  });
  if (!res.ok) return { error: errorText(t, res.error) };
  await refresh();
  redirect(await teachHref(`/courses/${res.data.id}`));
}

export async function saveLanding(courseId: string, _: FormState, fd: FormData): Promise<FormState> {
  const category = text(fd, "category_id");
  const body: Record<string, unknown> = {
    title: text(fd, "title"),
    subtitle: textOrNull(fd, "subtitle"),
    description: textOrNull(fd, "description"),
    category_id: category ? Number(category) : null,
    level: textOrNull(fd, "level"),
    medium: textOrNull(fd, "medium"),
    cover_image_url: textOrNull(fd, "cover_image_url"),
    promo_media_id: textOrNull(fd, "promo_media_id"),
  };
  // The address can change only until the first publish; the field is absent afterwards.
  if (fd.has("slug")) body.slug = text(fd, "slug");
  return patch(courseId, body);
}

export async function saveLearners(courseId: string, _: FormState, fd: FormData): Promise<FormState> {
  return patch(courseId, {
    learning_objectives: list(fd, "learning_objectives"),
    requirements: list(fd, "requirements"),
    target_audience: list(fd, "target_audience"),
  });
}

export async function savePricing(courseId: string, _: FormState, fd: FormData): Promise<FormState> {
  const pricing = text(fd, "pricing_model");
  if (pricing === "free") return patch(courseId, { pricing_model: "free", one_time_price_cents: null });
  const price = rupeesToCents(text(fd, "price"));
  if (price === null || price <= 0) return { error: t("classForm.invalidAmount") };
  return patch(courseId, { pricing_model: "one_time", one_time_price_cents: price });
}

export async function saveMessages(courseId: string, _: FormState, fd: FormData): Promise<FormState> {
  return patch(courseId, {
    welcome_message: textOrNull(fd, "welcome_message"), completion_message: textOrNull(fd, "completion_message"),
  });
}

export async function courseAction(courseId: string, action: "submit" | "withdraw" | "unpublish"): Promise<FormState> {
  return call(courseId, `~/courses/${courseId}/${action}`, "POST");
}

export async function deleteCourse(courseId: string): Promise<FormState> {
  const res = await api(`~/courses/${courseId}`, { method: "DELETE" });
  if (!res.ok) return { error: errorText(t, res.error) };
  await refresh();
  redirect(await teachHref("/courses"));
}

// --- curriculum ---------------------------------------------------------------------------

export async function addSection(courseId: string, _: FormState, fd: FormData): Promise<FormState> {
  return call(courseId, `~/courses/${courseId}/sections`, "POST", { title: text(fd, "title") });
}

export async function renameSection(courseId: string, sectionId: string, _: FormState, fd: FormData): Promise<FormState> {
  return call(courseId, `~/course-sections/${sectionId}`, "PATCH", { title: text(fd, "title") });
}

/** Swaps two neighbouring sections: each takes the other's position in the list. */
export async function swapSections(courseId: string, a: string, aIndex: number, b: string, bIndex: number): Promise<void> {
  const first = await call(courseId, `~/course-sections/${a}`, "PATCH", { sort_order: bIndex });
  if (!first.error) await call(courseId, `~/course-sections/${b}`, "PATCH", { sort_order: aIndex });
}

export async function deleteSection(courseId: string, sectionId: string): Promise<FormState> {
  return call(courseId, `~/course-sections/${sectionId}`, "DELETE");
}

export async function addLecture(courseId: string, sectionId: string, _: FormState, fd: FormData): Promise<FormState> {
  const type = text(fd, "lesson_type");
  return call(courseId, `~/course-sections/${sectionId}/lectures`, "POST", {
    title: text(fd, "title"),
    lesson_type: type,
    // An article needs text to exist; it starts with its title as a heading, to edit right away.
    article_body: type === "article" ? `# ${text(fd, "title")}\n` : null,
  });
}

export async function saveLecture(courseId: string, lectureId: string, _: FormState, fd: FormData): Promise<FormState> {
  const type = text(fd, "lesson_type");
  return call(courseId, `~/lectures/${lectureId}`, "PATCH", {
    title: text(fd, "title"),
    lesson_type: type,
    description: textOrNull(fd, "description"),
    ...(type === "article" ? { article_body: text(fd, "article_body") } : {}),
    is_free_preview: fd.get("is_free_preview") === "on",
    is_published: fd.get("is_published") === "on",
  });
}

export async function swapLectures(courseId: string, a: string, aIndex: number, b: string, bIndex: number): Promise<void> {
  const first = await call(courseId, `~/lectures/${a}`, "PATCH", { sort_order: bIndex });
  if (!first.error) await call(courseId, `~/lectures/${b}`, "PATCH", { sort_order: aIndex });
}

export async function deleteLecture(courseId: string, lectureId: string): Promise<FormState> {
  return call(courseId, `~/lectures/${lectureId}`, "DELETE");
}

export async function attachLectureFile(courseId: string, lectureId: string, _: FormState, fd: FormData): Promise<FormState> {
  const title = text(fd, "title");
  const res = await api(`~/lessons/${lectureId}/resources`, {
    method: "POST",
    body: { media_asset_id: text(fd, "media_asset_id"), title: title || null, is_downloadable: fd.get("is_downloadable") === "on" },
  });
  if (!res.ok) return { error: errorText(t, res.error) };
  await refresh(courseId);
  return { ok: true, at: Date.now() };
}

export async function removeLectureFile(courseId: string, resourceId: string): Promise<FormState> {
  const res = await api(`~/lesson-resources/${resourceId}`, { method: "DELETE" });
  if (!res.ok) return { error: errorText(t, res.error) };
  await refresh(courseId);
  return { ok: true };
}
