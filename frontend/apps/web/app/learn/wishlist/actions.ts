"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { api } from "@/lib/api";
import { getMe } from "@/lib/session";
import { errorText, t } from "@eduzone/lib/i18n";

/** Save or unsave a course. Guests sign in first and come back to `back`. */
export async function setSaved(courseId: string, saved: boolean, back: string): Promise<{ ok: true } | { ok: false; error: string }> {
  if (!(await getMe())) redirect(`/login?next=${encodeURIComponent(back.startsWith("/") ? back : "/courses")}`);
  const res = await api<string[]>(`/me/wishlist/${courseId}`, { method: saved ? "PUT" : "DELETE" });
  if (!res.ok) return { ok: false, error: errorText(t, res.error) };
  revalidatePath("/learn/wishlist");
  return { ok: true };
}
