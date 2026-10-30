import "server-only";

import { headers } from "next/headers";

import { WORKSPACE_HEADER } from "./workspace-header";

/** The console workspace (tenant slug) of this request: `/teach/<slug>/...` pages and the
 * Server Actions they post to. Null outside the console. */
export async function workspaceSlug(): Promise<string | null> {
  return (await headers()).get(WORKSPACE_HEADER);
}

/** A console link inside the current workspace: teachHref("/classes") → "/teach/<slug>/classes". */
export async function teachHref(path = ""): Promise<string> {
  const slug = await workspaceSlug();
  if (!slug) throw new Error("teachHref() used outside /teach/<slug>");
  return `/teach/${slug}${path}`;
}
