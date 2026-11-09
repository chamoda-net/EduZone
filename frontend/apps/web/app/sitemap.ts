import type { MetadataRoute } from "next";

import { api } from "@/lib/api";
import { mainOrigin } from "@/lib/site";
import type { Sitemap } from "@eduzone/lib/types";

/** Every public subject, teacher, class, institute, course, course category and instructor page (FRONTEND.md section 14). */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const origin = await mainOrigin();
  const res = await api<Sitemap>("/market/sitemap", { token: null });
  const paths = ["/", "/classes", "/courses", "/teachers", "/institutes", "/about", "/terms", "/privacy", "/refund-policy", "/contact"];
  if (res.ok) {
    paths.push(...res.data.subjects.map((s) => `/${s}`), ...res.data.teachers, ...res.data.classes, ...res.data.institutes);
    // Courses (docs/COURSES.md, step C2): landing pages, categories, instructors.
    paths.push(...(res.data.courses ?? []), ...(res.data.course_categories ?? []), ...(res.data.instructors ?? []));
  }
  return paths.map((path) => ({ url: `${origin}${path}`, changeFrequency: "daily" }));
}
