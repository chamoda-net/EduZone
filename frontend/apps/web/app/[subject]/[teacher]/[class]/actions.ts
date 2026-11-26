"use server";

import { redirect } from "next/navigation";

import type { Schema } from "@eduzone/api-client";
import { addToCart } from "@/app/cart/actions";
import { api } from "@/lib/api";
import { errorText, t } from "@eduzone/lib/i18n";

type Preview = Schema<"CoursePreviewOut">;
type Result = { ok: true; data: Preview } | { ok: false; error: string };

/** A short-lived stream of a free-preview lesson with a video (anyone may watch, no sign-in). */
export async function loadLessonPreview(lessonId: string): Promise<Result> {
  const res = await api<Preview>(`/market/lessons/${encodeURIComponent(lessonId)}/preview`, { method: "POST", token: null });
  return res.ok ? { ok: true, data: res.data } : { ok: false, error: errorText(t, res.error) };
}

/** The class page's main button: the open month (or a one-time class) into the cart, then the cart, where guests
 * sign in or register and pay. A student who already has it goes to the class in their area instead. */
export async function joinNow(classId: string, monthId: string | null): Promise<{ ok: false; error: string }> {
  const added = await addToCart(classId, monthId);
  if (!added.ok) {
    if (added.code === "ALREADY_HAS_ACCESS") redirect(`/learn/classes/${classId}`);
    return { ok: false, error: added.error };
  }
  redirect("/cart");                     // an item already in the cart is kept as it is (the API ignores repeats)
}
