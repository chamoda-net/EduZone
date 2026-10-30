import "server-only";

import { notFound } from "next/navigation";
import { cache } from "react";

import { api } from "./api";

/** A public marketplace read; 404s become the page's notFound(). Cached per request so
 * generateMetadata and the page share one call. */
export const market = cache(async <T,>(path: string): Promise<T> => {
  const res = await api<T>(`/market${path}`, { token: null });
  if (!res.ok) {
    if (res.status === 404 || res.status === 422) notFound();
    throw new Error(`market ${path}: ${res.error.code}`);
  }
  return res.data;
});

/** JSON-LD for search engines, safe to inline in a <script> tag. */
export function jsonLd(data: Record<string, unknown>): { __html: string } {
  return { __html: JSON.stringify(data).replace(/</g, "\\u003c") };
}
