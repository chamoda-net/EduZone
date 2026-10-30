import type { MetadataRoute } from "next";

import { mainOrigin } from "@/lib/site";

/** Public marketplace pages are indexed; the student area, consoles and sign-in pages are not. */
export default async function robots(): Promise<MetadataRoute.Robots> {
  const origin = await mainOrigin();
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/learn", "/teach", "/login", "/register", "/recover", "/verify-phone", "/verify-email", "/checkout", "/design", "/qr"] },
    sitemap: `${origin}/sitemap.xml`,
  };
}
