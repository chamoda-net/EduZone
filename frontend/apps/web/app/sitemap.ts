import type { MetadataRoute } from "next";

import { api } from "@/lib/api";
import { mainOrigin } from "@/lib/site";
import type { Sitemap } from "@eduzone/lib/types";

/** Every public subject, teacher, class and institute page (FRONTEND.md section 14). */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const origin = await mainOrigin();
  const res = await api<Sitemap>("/market/sitemap", { token: null });
  const paths = ["/", "/classes", "/teachers", "/institutes", "/about", "/terms", "/privacy", "/refund-policy", "/contact"];
  if (res.ok) {
    paths.push(...res.data.subjects.map((s) => `/${s}`), ...res.data.teachers, ...res.data.classes, ...res.data.institutes);
  }
  return paths.map((path) => ({ url: `${origin}${path}`, changeFrequency: "daily" }));
}
