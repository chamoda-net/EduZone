"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { api } from "@/lib/api";
import { colomboLocalToIso, rupeesToCents } from "@/lib/format";
import { errorText, t } from "@/lib/i18n";
import type { ClassItem, Lesson, Month } from "@/lib/types";

// The API checks permissions on every call; these actions only shape requests and errors.

export type FormState = { error?: string; ok?: boolean; at?: number };

const text = (fd: FormData, name: string) => String(fd.get(name) ?? "").trim();
const textOrNull = (fd: FormData, name: string) => text(fd, name) || null;
const intOrNull = (fd: FormData, name: string) => (text(fd, name) ? Number(text(fd, name)) : null);
const checked = (fd: FormData, name: string) => fd.get(name) === "on";

function classBody(fd: FormData): Record<string, unknown> | { error: string } {
  const pricing = text(fd, "pricing_model");
  let fee: number | null = null;
  if (pricing !== "free") {
    fee = rupeesToCents(text(fd, "fee"));
    if (fee === null) return { error: t("classForm.invalidAmount") };
  }
  return {
    title: text(fd, "title"),
    subject: textOrNull(fd, "subject"),
    exam: textOrNull(fd, "exam"),
    batch_year: intOrNull(fd, "batch_year"),
    medium: textOrNull(fd, "medium"),
    description: textOrNull(fd, "description"),
    pricing_model: pricing,
    monthly_fee_cents: pricing === "monthly" ? fee : null,
    one_time_price_cents: pricing === "one_time" ? fee : null,
    allow_late_months: checked(fd, "allow_late_months"),
    max_video_views: intOrNull(fd, "max_video_views"),
  };
}

function refresh(classId?: string) {
  revalidatePath("/org/classes");
  if (classId) revalidatePath(`/org/classes/${classId}`);
}

// --- classes ---------------------------------------------------------------------

export async function createClass(_: FormState, fd: FormData): Promise<FormState> {
  const body = classBody(fd);
  if ("error" in body) return { error: body.error as string };
  const res = await api<ClassItem>("/org/classes", { method: "POST", body });
  if (!res.ok) return { error: errorText(t, res.error) };
  refresh();
  redirect(`/org/classes/${res.data.id}`);
}

export async function updateClass(classId: string, _: FormState, fd: FormData): Promise<FormState> {
  const body = classBody(fd);
  if ("error" in body) return { error: body.error as string };
  const res = await api<ClassItem>(`/org/classes/${classId}`, { method: "PATCH", body });
  if (!res.ok) return { error: errorText(t, res.error) };
  refresh(classId);
  return { ok: true, at: Date.now() };
}

export async function setClassStatus(classId: string, status: string): Promise<FormState> {
  const res = await api(`/org/classes/${classId}`, { method: "PATCH", body: { status } });
  if (!res.ok) return { error: errorText(t, res.error) };
  refresh(classId);
  return { ok: true };
}

export async function deleteClass(classId: string): Promise<FormState> {
  const res = await api(`/org/classes/${classId}`, { method: "DELETE" });
  if (!res.ok) return { error: errorText(t, res.error) };
  refresh();
  redirect("/org/classes");
}

// --- months ----------------------------------------------------------------------

export async function createMonth(classId: string, _: FormState, fd: FormData): Promise<FormState> {
  const feeText = text(fd, "fee");
  const fee = feeText ? rupeesToCents(feeText) : null;
  if (feeText && fee === null) return { error: t("classForm.invalidAmount") };
  const res = await api<Month>(`/org/classes/${classId}/months`, {
    method: "POST",
    body: { month_start: `${text(fd, "month")}-01`, fee_cents: fee, status: text(fd, "status") || "open" },
  });
  if (!res.ok) return { error: errorText(t, res.error) };
  refresh(classId);
  return { ok: true, at: Date.now() };
}

export async function setMonthStatus(classId: string, monthId: string, status: string): Promise<FormState> {
  const res = await api(`/org/months/${monthId}`, { method: "PATCH", body: { status } });
  if (!res.ok) return { error: errorText(t, res.error) };
  refresh(classId);
  return { ok: true };
}

export async function deleteMonth(classId: string, monthId: string): Promise<FormState> {
  const res = await api(`/org/months/${monthId}`, { method: "DELETE" });
  if (!res.ok) return { error: errorText(t, res.error) };
  refresh(classId);
  return { ok: true };
}

// --- lessons ---------------------------------------------------------------------

export async function createLesson(classId: string, _: FormState, fd: FormData): Promise<FormState> {
  const type = text(fd, "lesson_type");
  const live = type === "live";
  const when = text(fd, "scheduled_at");
  const res = await api<Lesson>(`/org/classes/${classId}/lessons`, {
    method: "POST",
    body: {
      class_month_id: textOrNull(fd, "class_month_id"),
      title: text(fd, "title"),
      lesson_type: type,
      scheduled_at: live && when ? colomboLocalToIso(when) : null,
      duration_minutes: live ? intOrNull(fd, "duration_minutes") : null,
      zoom_join_url: live ? textOrNull(fd, "zoom_join_url") : null,
      is_published: checked(fd, "is_published"),
      is_free_preview: checked(fd, "is_free_preview"),
    },
  });
  if (!res.ok) return { error: errorText(t, res.error) };
  refresh(classId);
  return { ok: true, at: Date.now() };
}

export async function setLessonPublished(classId: string, lessonId: string, published: boolean): Promise<FormState> {
  const res = await api(`/org/lessons/${lessonId}`, { method: "PATCH", body: { is_published: published } });
  if (!res.ok) return { error: errorText(t, res.error) };
  refresh(classId);
  return { ok: true };
}

export async function deleteLesson(classId: string, lessonId: string): Promise<FormState> {
  const res = await api(`/org/lessons/${lessonId}`, { method: "DELETE" });
  if (!res.ok) return { error: errorText(t, res.error) };
  refresh(classId);
  return { ok: true };
}
