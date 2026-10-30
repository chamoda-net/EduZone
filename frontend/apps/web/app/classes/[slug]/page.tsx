import { notFound, redirect } from "next/navigation";

import { api } from "@/lib/api";
import { mainOrigin } from "@/lib/site";
import type { MarketClass, PublicClassDetail } from "@eduzone/lib/types";

/** Old tenant-site class links (<org>.eduzone…/classes/<slug>) now point to the marketplace page
 * (/<subject>/<teacher>/<class>), or to the class in the student area when it isn't listed. */
export default async function LegacyClassPage({ params }: PageProps<"/classes/[slug]">) {
  const { slug } = await params;
  const local = await api<PublicClassDetail>(`/public/classes/${encodeURIComponent(slug)}`, { token: null });
  if (!local.ok) notFound();
  const listed = await api<MarketClass>(`/market/classes/by-id/${local.data.class.id}`, { token: null });
  redirect(`${await mainOrigin()}${listed.ok ? listed.data.path : `/learn/classes/${local.data.class.id}`}`);
}
