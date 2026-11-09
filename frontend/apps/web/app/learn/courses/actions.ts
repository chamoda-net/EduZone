"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import type { Schema } from "@eduzone/api-client";
import { addToCart } from "@/app/cart/actions";
import { api } from "@/lib/api";
import { getMe } from "@/lib/session";
import { errorText, t } from "@eduzone/lib/i18n";

type Result = { ok: true } | { ok: false; error: string };

/** A free course: enrol, then straight into the player. Not signed in: sign in first and come back. */
export async function enrollCourse(courseId: string, slug: string): Promise<Result> {
  if (!(await getMe())) redirect(`/login?next=${encodeURIComponent(`/course/${slug}`)}`);
  const res = await api<Schema<"LearnCourse">>(`/learn/courses/${courseId}/enroll`, { method: "POST" });
  if (!res.ok) return { ok: false, error: errorText(t, res.error) };
  revalidatePath("/learn/courses");
  redirect(`/learn/courses/${courseId}`);
}

/** "Buy now": into the cart (the guest cart for visitors), then the cart page. */
export async function buyNow(courseId: string): Promise<Result> {
  const added = await addToCart(courseId, null);
  if (!added.ok && added.error) return { ok: false, error: added.error };
  redirect("/cart");
}

export async function setLectureComplete(courseId: string, lectureId: string, done: boolean): Promise<Result> {
  const res = await api(`/learn/lectures/${lectureId}/complete`, { method: done ? "POST" : "DELETE" });
  if (!res.ok) return { ok: false, error: errorText(t, res.error) };
  revalidatePath(`/learn/courses/${courseId}`);
  return { ok: true };
}

export async function saveReview(courseId: string, rating: number, comment: string): Promise<Result> {
  const res = await api(`/learn/courses/${courseId}/review`, {
    method: "PUT", body: { rating, comment: comment.trim() || null },
  });
  if (!res.ok) return { ok: false, error: errorText(t, res.error) };
  revalidatePath(`/learn/courses/${courseId}`);
  return { ok: true };
}

export async function deleteReview(courseId: string): Promise<Result> {
  const res = await api(`/learn/courses/${courseId}/review`, { method: "DELETE" });
  if (!res.ok) return { ok: false, error: errorText(t, res.error) };
  revalidatePath(`/learn/courses/${courseId}`);
  return { ok: true };
}
