"use server";

import { revalidatePath } from "next/cache";

import { api } from "@/lib/api";
import { teachHref } from "@/lib/workspace";
import { errorText, t } from "@eduzone/lib/i18n";
import type { TeacherProfile } from "@eduzone/lib/types";

export type ProfileState = { error?: string; ok?: boolean; at?: number };

/** Saves the signed-in teacher's public profile (one per person, shared by every workspace). */
export async function saveProfile(_: ProfileState, fd: FormData): Promise<ProfileState> {
  const field = (name: string) => String(fd.get(name) ?? "").trim();
  const res = await api<TeacherProfile>("/me/teacher-profile", {
    method: "PUT",
    body: {
      slug: field("slug").toLowerCase(),
      display_name: field("display_name"),
      headline: field("headline") || null,
      bio: field("bio") || null,
      photo_url: field("photo_url") || null,
      highlights: field("highlights").split("\n").map((h) => h.trim()).filter(Boolean).slice(0, 6),
    },
  });
  if (!res.ok) return { error: errorText(t, res.error) };
  revalidatePath(await teachHref("/profile"));
  return { ok: true, at: Date.now() };
}
