import "server-only";

import { headers } from "next/headers";

import { userHost } from "./api";

const BASE_DOMAIN = (process.env.BASE_DOMAIN ?? "localhost").toLowerCase();

/** The main site (BASE_DOMAIN, e.g. eduzone.switchops.tech; `localhost` in development): no
 * tenant in the host. Tenant subdomains only redirect to it since the marketplace (phase 4). */
export async function isMainHost(): Promise<boolean> {
  return (await userHost()).toLowerCase().split(":")[0] === BASE_DOMAIN;
}

/** Scheme + host of this request, e.g. "https://eduzone.switchops.tech" (share links, canonical URLs). */
export async function siteOrigin(): Promise<string> {
  const proto = (await headers()).get("x-forwarded-proto") ?? (process.env.NODE_ENV === "production" ? "https" : "http");
  return `${proto}://${await userHost()}`;
}

/** The main site's origin, keeping this request's port (development runs on :3000). */
export async function mainOrigin(): Promise<string> {
  const origin = new URL(await siteOrigin());
  origin.hostname = BASE_DOMAIN;
  return origin.origin;
}
